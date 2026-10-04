# BAB 07: Manajemen Memori Dinamis, Subalokator & Profiling
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Keterbatasan Alokator Standar (`ptmalloc3`)**: Mengidentifikasi titik kritis degradasi latensi (*lock contention*, *cache thrashing*, dan *false sharing*) pada sistem berkonkurensi tinggi.
2. **Merancang Subalokator Memori Khusus (*Custom Suballocators*)**: Mengimplementasikan *Arena (Monotonic/Linear)*, *Fixed-Size Block (Pool)*, dan *Segregated Free-List Allocator* yang memenuhi batas keselarasan perangkat keras (*hardware cache-line alignment*).
3. **Mengeliminasi Fragmentasi Memori**: Menggunakan teknik *intrusive singly/doubly linked lists* dan *coalescing* untuk mengeliminasi fragmentasi eksternal serta menekan fragmentasi internal hingga $< 5\%$.
4. **Mengimplementasikan Strategi Thread-Local & Lock-Free Allocation**: Membangun arsitektur subalokasi berbasis *Thread-Caching* (menyerupai arsitektur inti TCMalloc/Jemalloc) guna mencapai alokasi deterministik $\mathcal{O}(1)$.
5. **Memvalidasi Integritas Memori Produksi**: Mengintegrasikan sistem *canary byte poisoning*, *redzone verification*, dan isolasi memori berbasis POSIX `mmap`/`mprotect`.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* **Arsitektur Sistem Komputer**: Paging virtual memori, Translation Lookaside Buffer (TLB), cache hierarchies (L1d, L2, L3), dan cache-line sizing (x86-64 standar 64 byte).
* **Pointer Arithmetic Lanjutan**: `uintptr_t`, manipulasi bit masking, casting pointer ganda (`void**`), dan dereferensi berbasis offset (`offsetof`).
* **Sistem Memori OS (POSIX)**: Antarmuka syscall `mmap(2)`, `munmap(2)`, `madvise(2)`, `brk(2)`/`sbrk(2)`.
* **Standar C11/C17 Memory Model**: `max_align_t`, `alignof`, `aligned_alloc`, dan atomik bawaan (`stdatomic.h`).

---

### 3. Concept & Internal Architecture

#### 3.1 Mengapa `malloc(3)` Standar Gagal pada Sistem Skala Enterprise?
Implementasi alokator bawaan GNU C Library (`ptmalloc`), meskipun serbaguna (*general purpose*), memiliki overhead struktural yang signifikan untuk sistem berperforma tinggi:
1. **Metadata In-band**: Setiap chunk menyimpan metadata (`size_t mchunk_size`) tepat di depan payload. Hal ini menyebabkan:
   - Polusi cache L1: Pembacaan data payload sering kali memuat metadata chunk berikutnya ke dalam cache line yang sama.
   - Kerentanan keamanan: *Heap buffer overflow* dapat merusak metadata chunk di sebelahnya (*heap metadata corruption*).
2. **Global Heap Mutex / Arena Contention**: Meskipun `ptmalloc` memiliki beberapa arena (`32 * core_count` pada x86-64), thread yang memetakan arena yang sama akan tersendat (*blocked*) oleh *lock contention* saat memanggil `malloc` dan `free` frekuensi tinggi.
3. **Fragmentasi Eksternal**: Pola alokasi dan dealokasi objek dengan berbagai ukuran (*interleaved sizes*) menyebabkan memori virtual berlubang (*fragmented*), sehingga sistem tidak dapat mengalokasikan blok besar meskipun total memori bebas mencukupi.

```
       ptmalloc Chunk Layout (In-Band Metadata)
+--------------------------------+---------------------------------+
| Prev Size (if prev is free)    | Size of Chunk | A | M | P Flags |
+--------------------------------+---------------------------------+ <-- Payload Pointer (User)
| Payload Data...                                                  |
| ...                                                              |
+------------------------------------------------------------------+
```

#### 3.2 Arsitektur Subalokator Khusus

##### A. Monotonic / Linear Arena Allocator
Alokator paling deterministik. Memori dialokasikan secara sekuensial melalui pergeseran pointer *offset*. Dealokasi tidak dilakukan per objek, melainkan seluruh arena di-reset secara bersamaan ($\mathcal{O}(1)$).
* **Karakteristik**: Latensi alokasi konstan ($\approx 3-5$ siklus CPU), fragmentasi eksternal nol, pemanfaatan cache temporal maksimal.
* **Kasus Penggunaan**: Pemrosesan per-request (HTTP request lifecycle, parser JSON/AST, per-frame rendering loop).

##### B. Fixed-Size Block (Pool / Slab) Allocator
Memecah satu blok memori besar menjadi potongan-potongan seragam (*chunks*). Bagian blok yang belum terpakai ditautkan menggunakan teknik **Intrusive Free-List**: pointer penunjuk node berikutnya disimpan langsung di dalam ruang data blok kosong tersebut tanpa menambah overhead memori sama sekali.
* **Karakteristik**: Alokasi $\mathcal{O}(1)$, dealokasi $\mathcal{O}(1)$, fragmentasi eksternal nol.
* **Overhead Internal**: Fragmentasi internal terjadi jika ukuran objek lebih kecil dari ukuran blok minimum (`sizeof(void*)` = 8 byte pada x86-64).

```
          Intrusive Free-List Memory Pool Architecture
       +-------------------------------------------------------+
       |                      Arena Heap                       |
       +-------------------------------------------------------+
       | Block 0     | Block 1     | Block 2     | Block 3     |
       | [Payload]   | [NextPtr]---+->[NextPtr]--+-> NULL      |
       | (Allocated) | (Free)      | (Free)      | (Free)      |
       +-------------+-------------+-------------+-------------+
                            ^
FreeList Head --------------+
```

##### C. Thread-Caching Suballocator (Model Produksi)
Mengombinasikan Pool Allocator dengan isolasi thread (*Thread Local Storage / TLS*). Setiap thread memiliki alokator lokal untuk kelas ukuran kecil (*size-classes*), mengeliminasi locking dan menghindari *false sharing* antar core CPU.

---

### 4. Why & What

| Tipe Alokator | Kompleksitas Waktu (Alloc) | Kompleksitas Waktu (Free) | Fragmentasi Eksternal | Masalah Utama | Penggunaan Ideal |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **System `malloc`** | $\mathcal{O}(1) - \mathcal{O}(N)$ | $\mathcal{O}(1) - \mathcal{O}(N)$ | Tinggi | Mutex Contention, Cache Pollution | General software, ukuran tidak terduga |
| **Arena (Linear)** | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ (Reset all) | Nol | Tidak bisa dealokasi parsial | Parsing, HTTP Request Scope, Game Frames |
| **Pool (Fixed-Size)**| $\mathcal{O}(1)$ | $\mathcal{O}(1)$ | Nol | Ukuran objek harus homogen | Network Packets, Database Tuples, ECS |
| **Buddy Allocator** | $\mathcal{O}(\log N)$ | $\mathcal{O}(\log N)$ | Rendah | Fragmentasi internal tinggi ($2^k$) | OS Page Allocator, Buffer Kernel |

---

### 5. How: Workflow Detail Penyelarasan Memori (Alignment Logic)

Agar CPU dapat memproses instruksi SIMD (misal: SSE, AVX-512) secara efisien dan mencegah *unaligned memory access penalties*, pointer payload wajib diselaraskan dengan batas pangkat dua (*power-of-two alignment*).

Formulanya:
$$\text{aligned\_addr} = (\text{addr} + (\text{alignment} - 1)) \ \& \ \sim(\text{alignment} - 1)$$

```
Offset Calculation Flow:
1. Current Pointer : 0x1003 (4099)
2. Alignment Req   : 8 (0x0008)
3. Mask Calculation: ~(8 - 1) = ~7 = ...11111000
4. Add & Mask      : (0x1003 + 7) & (~7)
                   : 0x100A & ...11111000
                   : 0x1008 (4104) -> Aligned Address!
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Hotel dan Lahan Parkir
* **`malloc` Standar (Valet Parkir Kota)**: Setiap kendaraan (mobil, motor, bus) diparkir di sembarang tempat kosong. Petugas harus mencatat posisi setiap kendaraan di buku besar. Lama-kelamaan, terbentuk celah kosong yang hanya cukup untuk motor, padahal yang datang kemudian adalah bus (fragmentasi eksternal).
* **Arena Allocator (Buku Kas Bon Fisik)**: Anda menulis transaksi pada buku kas baris demi baris secara berurutan. Anda tidak menghapus satu baris di tengah; saat transaksi selesai dalam satu siklus harian, Anda menyobek seluruh halaman dan mulai dari lembar baru.
* **Pool Allocator (Rak Helm Standar)**: Rak modular dengan 100 kompartemen identik. Setiap slot hanya muat 1 helm. Mengambil helm dari slot manapun butuh waktu 1 detik. Menaruhnya kembali butuh waktu 1 detik. Celah kosong tidak akan pernah tercecer tidak teratur.

```
+=============================================================================+
|                      STRUKTUR KONTIGU POOL SUBALOKATOR                      |
+=============================================================================+
| [Block 0] 64-Bytes Cache Aligned                                            |
| +-------------------------------------------------------------------------+ |
| | Ptr to Block 1 (Saat Kosong) ATAU User Data Buffer (Saat Digunakan)      | |
| +-------------------------------------------------------------------------+ |
| [Block 1] 64-Bytes Cache Aligned                                            |
| +-------------------------------------------------------------------------+ |
| | Ptr to Block 2 (Saat Kosong) ATAU User Data Buffer (Saat Digunakan)      | |
| +-------------------------------------------------------------------------+ |
| [Block 2] 64-Bytes Cache Aligned                                            |
| +-------------------------------------------------------------------------+ |
| | NULL (Ekor Daftar Free)                                                 | |
| +-------------------------------------------------------------------------+ |
+=============================================================================+
```

---

### 7. Implementasi Kode Tingkat Produksi

#### 7.1 Simple Example: High-Performance Linear Arena Allocator
File: `arena_allocator.c`

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>

typedef struct {
    uint8_t *buffer;
    size_t   capacity;
    size_t   offset;
    size_t   prev_offset;
} Arena;

static inline uintptr_t align_forward(uintptr_t ptr, size_t alignment) {
    assert((alignment & (alignment - 1)) == 0 && "Alignment must be a power of two");
    return (ptr + (alignment - 1)) & ~(uintptr_t)(alignment - 1);
}

Arena arena_create(size_t capacity) {
    Arena arena = {0};
    arena.buffer = (uint8_t *)malloc(capacity);
    if (arena.buffer) {
        arena.capacity = capacity;
        arena.offset = 0;
        arena.prev_offset = 0;
    }
    return arena;
}

void *arena_alloc_align(Arena *arena, size_t size, size_t alignment) {
    uintptr_t current_ptr = (uintptr_t)arena->buffer + arena->offset;
    uintptr_t aligned_ptr = align_forward(current_ptr, alignment);
    size_t padding = aligned_ptr - current_ptr;

    if (arena->offset + padding + size > arena->capacity) {
        return NULL; // Out of memory
    }

    arena->prev_offset = arena->offset;
    arena->offset += padding + size;

    return (void *)aligned_ptr;
}

void *arena_alloc(Arena *arena, size_t size) {
    return arena_alloc_align(arena, size, sizeof(max_align_t));
}

void arena_reset(Arena *arena) {
    arena->offset = 0;
    arena->prev_offset = 0;
}

void arena_destroy(Arena *arena) {
    if (arena->buffer) {
        free(arena->buffer);
        arena->buffer = NULL;
    }
    arena->capacity = 0;
    arena->offset = 0;
}
```

#### 7.2 Practical Example: Enterprise-Grade Cache-Aligned Pool Allocator
Alokator ini menggunakan memori virtual OS langsung (`mmap`), struktur *intrusive free-list*, isolasi memori dengan *canary byte*, dan keselarasan penuh terhadap *L1 Data Cache line* (64-byte).

File: `pool_allocator.h`
```c
#ifndef POOL_ALLOCATOR_H
#define POOL_ALLOCATOR_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#define CACHE_LINE_SIZE 64
#define CANARY_VALUE    0xDEADBEEFCAFECAFEULL

typedef struct PoolAllocator PoolAllocator;

PoolAllocator *pool_create(size_t object_size, size_t capacity);
void          *pool_alloc(PoolAllocator *pool);
void           pool_free(PoolAllocator *pool, void *ptr);
void           pool_destroy(PoolAllocator *pool);
size_t         pool_available_slots(const PoolAllocator *pool);

#endif // POOL_ALLOCATOR_H
```

File: `pool_allocator.c`
```c
#define _GNU_SOURCE
#include "pool_allocator.h"
#include <sys/mman.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>

typedef struct FreeNode {
    struct FreeNode *next;
} FreeNode;

typedef struct {
    uint64_t canary;
} ChunkHeader;

struct PoolAllocator {
    void        *raw_memory;       // Pointer awal mmap
    size_t       total_mmap_size;  // Total ukuran alokasi mmap
    FreeNode    *free_list_head;   // Kepala antrean free list
    size_t       chunk_stride;     // Jarak antar chunk yang sudah dialineasi
    size_t       object_size;      // Ukuran objek yang diminta user
    size_t       capacity;         // Kapasitas maksimum objek
    size_t       allocated_count;  // Jumlah objek aktif
};

static inline size_t align_up(size_t value, size_t alignment) {
    return (value + (alignment - 1)) & ~(alignment - 1);
}

PoolAllocator *pool_create(size_t object_size, size_t capacity) {
    if (object_size == 0 || capacity == 0) return NULL;

    // Minimum payload harus bisa memuat intrusive pointer saat statusnya kosong
    size_t effective_payload = object_size < sizeof(FreeNode) ? sizeof(FreeNode) : object_size;
    
    // Setiap chunk memuat [ChunkHeader (Canary)] + [Effective Payload]
    size_t required_chunk_size = sizeof(ChunkHeader) + effective_payload;
    
    // Pastikan setiap chunk dimulai tepat pada batas Cache-Line (64 byte)
    size_t chunk_stride = align_up(required_chunk_size, CACHE_LINE_SIZE);

    size_t total_memory = chunk_stride * capacity;
    
    // Normalisasi ke batas page size OS (4096 byte)
    long page_size = sysconf(_SC_PAGESIZE);
    if (page_size < 0) page_size = 4096;
    size_t mapped_size = align_up(total_memory, (size_t)page_size);

    // Alokasi memori virtual non-swapable & zero-initialized
    void *mem = mmap(NULL, mapped_size, PROT_READ | PROT_WRITE, 
                     MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mem == MAP_FAILED) {
        return NULL;
    }

    PoolAllocator *pool = (PoolAllocator *)malloc(sizeof(PoolAllocator));
    if (!pool) {
        munmap(mem, mapped_size);
        return NULL;
    }

    pool->raw_memory = mem;
    pool->total_mmap_size = mapped_size;
    pool->chunk_stride = chunk_stride;
    pool->object_size = object_size;
    pool->capacity = capacity;
    pool->allocated_count = 0;

    // Inisialisasi Intrusive Free-List
    pool->free_list_head = NULL;
    for (size_t i = 0; i < capacity; ++i) {
        uint8_t *chunk_base = (uint8_t *)pool->raw_memory + (i * chunk_stride);
        
        // Pasang header canary
        ChunkHeader *header = (ChunkHeader *)chunk_base;
        header->canary = CANARY_VALUE;

        // Pointer payload berada tepat setelah header
        FreeNode *node = (FreeNode *)(chunk_base + sizeof(ChunkHeader));
        node->next = pool->free_list_head;
        pool->free_list_head = node;
    }

    return pool;
}

void *pool_alloc(PoolAllocator *pool) {
    assert(pool != NULL);

    if (pool->free_list_head == NULL) {
        // Pool exhausted (OOM)
        return NULL;
    }

    // Ambil node teratas dari free list: O(1)
    FreeNode *node = pool->free_list_head;
    pool->free_list_head = node->next;
    pool->allocated_count++;

    // Validasi integritas header canary sebelum diserahkan ke user
    uint8_t *chunk_base = (uint8_t *)node - sizeof(ChunkHeader);
    ChunkHeader *header = (ChunkHeader *)chunk_base;
    if (header->canary != CANARY_VALUE) {
        fprintf(stderr, "[FATAL] Memory Corruption terdeteksi pada Canary Chunk: %p\n", (void*)header);
        abort();
    }

    return (void *)node;
}

void pool_free(PoolAllocator *pool, void *ptr) {
    if (!ptr || !pool) return;

    // Validasi apakah pointer berada di dalam rentang alokasi pool kita
    uintptr_t addr = (uintptr_t)ptr;
    uintptr_t start = (uintptr_t)pool->raw_memory;
    uintptr_t end = start + (pool->chunk_stride * pool->capacity);

    if (addr < start || addr >= end) {
        fprintf(stderr, "[FATAL] Bad Free: Pointer %p berada di luar rentang pool!\n", ptr);
        abort();
    }

    // Validasi offset alignment
    size_t offset_from_start = addr - start;
    if ((offset_from_start - sizeof(ChunkHeader)) % pool->chunk_stride != 0) {
        fprintf(stderr, "[FATAL] Misaligned Free: Pointer %p bukan awal blok!\n", ptr);
        abort();
    }

    // Validasi Canary Integrity
    ChunkHeader *header = (ChunkHeader *)((uint8_t *)ptr - sizeof(ChunkHeader));
    if (header->canary != CANARY_VALUE) {
        fprintf(stderr, "[FATAL] Double-free atau Out-of-bounds write terdeteksi pada Canary: %p\n", ptr);
        abort();
    }

    // Kembalikan ke kepala free-list (LIFO logic): O(1)
    FreeNode *node = (FreeNode *)ptr;
    node->next = pool->free_list_head;
    pool->free_list_head = node;
    pool->allocated_count--;
}

size_t pool_available_slots(const PoolAllocator *pool) {
    if (!pool) return 0;
    return pool->capacity - pool->allocated_count;
}

void pool_destroy(PoolAllocator *pool) {
    if (!pool) return;
    if (pool->raw_memory) {
        munmap(pool->raw_memory, pool->total_mmap_size);
    }
    free(pool);
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Ultra-Low Latency High-Frequency Trading (HFT) Matching Engine
* **Kebutuhan**: Memproses rata-rata 10 juta event per detik (*Order Insertion, Cancellation, Execution*). Batas toleransi latensi per transaksi: $P99.9 < 800\text{ ns}$.
* **Permasalahan Lapangan**: 
  Implementasi awal menggunakan `malloc()` standar saat pembentukan objek order `struct OrderBookEntry`. Setiap beberapa menit, terjadi lonjakan latensi (*jitter*) hingga $> 120\,\mu\text{s}$.
* **Akar Masalah (Root Cause Analysis)**:
  1. **Lock Contention**: Thread pembaca *UDP Multicast Feed* dan thread eksekusi memperebutkan lock arena heap internal glibc.
  2. **Page Fault Latency**: Saat glibc memanggil kernel `brk()` atau `mmap()` secara sporadis untuk memperluas heap, CPU dialihkan ke mode kernel.
  3. **TLB Misses**: Alokasi tersebar di ratusan rentang virtual memory yang tidak berdekatan.

#### Arsitektur Solusi
```
+-----------------------------------------------------------------------------------+
|                        HFT MEMORY SUBSYSTEM ARCHITECTURE                          |
+-----------------------------------------------------------------------------------+
| Network Thread 0 (Core 2)      | Network Thread 1 (Core 4)                        |
|                                |                                                  |
| TLS Pool Allocator (64B Chunk) | TLS Pool Allocator (64B Chunk)                   |
| (100K Preallocated Orders)     | (100K Preallocated Orders)                       |
|                 \              |              /                                   |
|                  \             |             /                                    |
|             Zero-Copy Single Producer Single Consumer (SPSC) RingBuffer           |
|                                |                                                  |
|                                v                                                  |
|                    Core Matching Engine (Core 6)                                  |
|                    Arena Allocator (Per-Tick Reset)                               |
+-----------------------------------------------------------------------------------+
```

* **Hasil Implementasi**:
  1. *Jitter* berkurang drastis: $P99.9$ turun dari $120\,\mu\text{s}$ menjadi $450\text{ ns}$.
  2. *Throughput* naik dari $1.8\text{M ops/sec}$ ke $14.2\text{M ops/sec}$.
  3. Konsumsi kernel CPU time (System Call Overhead) turun menjadi $0\%$.

---

### 9. Trade-offs

| Desain Arsitektur | Keuntungan | Biaya/Konsekuensi |
| :--- | :--- | :--- |
| **Cache-line Alignment (64 byte pad)** | Menghilangkan *split-cache line penalty*; meningkatkan kecepatan akses SIMD/AVX. | Terjadi pemborosan ruang (*slack space*) jika ukuran objek kecil (misal payload 16 byte $\to$ 48 byte terbuang). |
| **Intrusive Pointers** | Menghemat metadata overhead; tidak ada konsumsi memori tambahan untuk struktur link. | Objek terkecil dibatasi minimal `sizeof(uintptr_t)` (8 byte). Kode menjadi *unsafe* jika terjadi pointer corrupt. |
| **Canary Validation Byte** | Mampu mendeteksi korupsi memori (*out-of-bounds write*, double-free) seketika tanpa debugger. | Menambah instruksi CPU check pada alur alokasi dan memakan 8 byte memori per chunk. |
| **Static Preallocation via `mmap`** | Menghilangkan runtime syscall latencies; zero-jitter allocation. | Membutuhkan estimasi kapasitas awal (*upfront capacity planning*). Potensi OOM fatal jika pool habis. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Perhitungan Penyelarasan (Alignment Masking Bug)
```c
// BUG FATAL:
#define BAD_ALIGN(sz, align) ((sz + align) & ~align) 
// Jika align=8: ~align adalah ~8 = ...11110111 (BUKAN bitmask pangkat 2 yang benar)

// PERBAIKAN:
#define GOOD_ALIGN(sz, align) (((sz) + ((align) - 1)) & ~((align) - 1))
```

#### 2. Korupsi Data Akibat Re-use Intrusive Pointer
```c
// BUG: Menulis payload sebelum node dikeluarkan dari pool dengan benar
void *ptr = pool_alloc(pool);
// Menghapus data tanpa peduli alignment/canary...
memset(ptr, 0, sizeof(MyData)); 
// Jika salah hitung offset pointer, canary terhapus -> crash saat pool_free()
```

#### 3. Diagnosis Menggunakan Compiler Flags & Sanitizer
Saat membangun subalokator, gunakan instrumen berikut secara konsisten:
```bash
# Aktifkan AddressSanitizer dengan integrasi kustom
gcc -O2 -g -fsanitize=address,undefined -Wall -Wextra -pedantic main.c pool_allocator.c -o app
```
*Gunakan antarmuka ASan Annotation untuk mendeteksi use-after-free pada custom pool Anda:*
```c
#include <sanitizer/asan_interface.h>
// Saat dialokasikan:
ASAN_UNPOISON_MEMORY_REGION(payload_ptr, user_size);
// Saat didealokasikan (free):
ASAN_POISON_MEMORY_REGION(payload_ptr, chunk_size);
```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Validasi Power-of-Two**: Selalu gunakan `assert((align & (align - 1)) == 0)` sebelum melakukan operasi bitwise alignment.
2. [ ] **Alokasikan Berbasis Page**: Subalokator berskala besar wajib mengambil memori dalam kelipatan ukuran virtual memory page (biasanya 4096 byte).
3. [ ] **Lock-Memory (mlock)**: Pada aplikasi *mission-critical* (misalnya HFT), panggil `mlock()` pada blok memori yang di-`mmap` untuk mencegah kernel swap ke disk (*paging avoidance*).
4. [ ] **Bebaskan Secara Massal**: Utamakan reset siklis (*batch deallocation*) menggunakan Arena daripada pelacakan objek individual di jalur kritis.
5. [ ] **Intrusive Node Minimum Guard**: Berikan garansi `sizeof(T) >= sizeof(void*)` dengan bantuan `_Static_assert`.
6. [ ] **Boundary Verification**: Setiap pemanggilan `free` wajib memvalidasi apakah pointer berada di dalam batas alokasi (`ptr >= start && ptr < end`).
7. [ ] **Canary Isolation**: Pisahkan metadata write-tracking canary minimal 8-byte sebelum payload untuk menghindari *silent corruption*.
8. [ ] **Non-Contended Locks**: Jika multithreading mutlak diperlukan, gunakan teknik *Thread-Local Cache* (TLS) atau *Single-Producer Single-Consumer* queues alih-alih meletakkan `pthread_mutex_t` pada fungsi `alloc()`.

---

### 12. Hands-on Practice

Buatlah direktori praktikum dengan hierarki berikut:
```
hands-on/
└── m02/
    ├── Makefile
    ├── src/
    │   ├── main.c
    │   ├── pool_allocator.c
    │   └── pool_allocator.h
    └── tests/
        └── test_bench.c
```

#### File: `hands-on/m02/tests/test_bench.c`
```c
#include "../src/pool_allocator.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <assert.h>

#define ITERATIONS 2000000
#define BATCH_SIZE 1024

static inline double get_time_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (ts.tv_sec * 1e9) + ts.tv_nsec;
}

int main(void) {
    printf("[*] Benchmarking Pool Allocator vs System malloc...\n");

    PoolAllocator *pool = pool_create(sizeof(uint64_t) * 4, BATCH_SIZE);
    assert(pool != NULL);

    void *ptrs[BATCH_SIZE];

    // Benchmark Pool Allocator
    double start_pool = get_time_ns();
    for (int it = 0; it < (ITERATIONS / BATCH_SIZE); ++it) {
        for (int i = 0; i < BATCH_SIZE; ++i) {
            ptrs[i] = pool_alloc(pool);
        }
        for (int i = 0; i < BATCH_SIZE; ++i) {
            pool_free(pool, ptrs[i]);
        }
    }
    double total_pool_time = get_time_ns() - start_pool;
    printf("[+] Custom Pool Allocator Time: %f ms\n", total_pool_time / 1e6);

    // Benchmark System malloc
    double start_malloc = get_time_ns();
    for (int it = 0; it < (ITERATIONS / BATCH_SIZE); ++it) {
        for (int i = 0; i < BATCH_SIZE; ++i) {
            ptrs[i] = malloc(sizeof(uint64_t) * 4);
        }
        for (int i = 0; i < BATCH_SIZE; ++i) {
            free(ptrs[i]);
        }
    }
    double total_malloc_time = get_time_ns() - start_malloc;
    printf("[+] System malloc/free Time    : %f ms\n", total_malloc_time / 1e6);
    printf("[*] Latency Multiplier Speedup : %.2fx faster!\n", total_malloc_time / total_pool_time);

    pool_destroy(pool);
    return 0;
}
```

#### Instruksi Eksekusi:
```bash
# Masuk ke direktori
cd hands-on/m02/

# Kompilasi dengan optimasi tinggi
gcc -O3 -Wall -Wextra -std=c11 src/pool_allocator.c tests/test_bench.c -o tests/benchmark_bin

# Jalankan profiling
./tests/benchmark_bin
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi Arena Allocator pada Bagian 7.1 agar memiliki fitur `arena_save()` dan `arena_restore(size_t checkpoint)`. Hal ini memungkinkan memori di-rewind sebagian tanpa harus menghapus seluruh arena.
* **Kebutuhan**: Implementasi fungsi `size_t arena_save(const Arena *arena)` dan `void arena_restore(Arena *arena, size_t checkpoint)`.

#### Level Medium
Tambahkan proteksi konkurensi berbasis *POSIX Spinlock* (`pthread_spinlock_t`) pada implementasi `PoolAllocator` yang ada di bagian 7.2. Lakukan profiling perbandingan *contention overhead* menggunakan 4 thread secara paralel dibandingkan alokasi `malloc()` standar.

#### Level Hard
Rancang dan bangun **Buddy Allocator** minimalis:
* Total memori: 1MB.
* Minimal chunk alokasi: 4KB (1 OS page), maksimal 1MB.
* Terapkan algoritma *split* saat blok berukuran lebih besar dibutuhkan dan *coalescing* (penggabungan blok buddy) saat dealokasi menggunakan manipulasi operasi XOR address:
$$\text{buddy\_address} = \text{block\_address} \oplus \text{block\_size}$$

---

### 14. Challenge

**Skenario**: Bangun sebuah **Lock-Free Thread-Cached Slab Allocator** untuk memproses packet frame UDP pada arsitektur multi-core (NUMA-aware).
* **Spesifikasi**:
  1. Terdiri dari minimal 3 *Slab Classes* (ukuran chunk: 64B, 512B, 2048B).
  2. Alokasi chunk kecil harus diselesaikan secara murni via Thread-Local Storage (`__thread` pointer cache) tanpa atomic instructions pada jalur cepat (*fast path*).
  3. Apabila local cache thread habis, thread diperbolehkan mengambil *batch of blocks* dari global slab allocator menggunakan antarmuka lock-free stack berbasis `atomic_compare_exchange_weak`.
  4. Atasi potensi **ABA Problem** pada lock-free linked list dengan mengimplementasikan tagged pointer (pointer packing 64-bit yang memuat address 48-bit + counter 16-bit).
  5. Program tidak boleh menghasilkan *memory leak* atau *thread contention deadlock* saat diuji dengan 16 core CPU yang menghasilkan beban alokasi/dealokasi silang antar thread.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic Concepts (5 Soal)
1. **Mengapa *internal fragmentation* terjadi pada Pool Allocator?**
   - *Jawaban*: Karena ukuran objek pengguna yang dialokasikan lebih kecil daripada ukuran tetap (*fixed chunk size*) yang disiapkan oleh pool alokator.
2. **Apa yang dimaksud dengan manipulasi `intrusive list` dalam konteks subalokator memori?**
   - *Jawaban*: Menggunakan ruang payload memori kosong itu sendiri untuk menyimpan pointer `next` penunjuk node berikutnya, sehingga tidak memakan metadata terpisah.
3. **Mengapa alignment wajib merupakan bilangan pangkat dua ($2^n$)?**
   - *Jawaban*: Agar operasi keselarasan alamat memori dapat dieksekusi secara instan pada tingkat CPU menggunakan masking bitwise `& ~(alignment - 1)`, bukan instruksi pembagian modulo yang lambat.
4. **Apa fungsi parameter `MAP_ANONYMOUS` pada syscall `mmap`?**
   - *Jawaban*: Menginstruksikan kernel bahwa pemetaan memori tidak didukung (*backed*) oleh file disk apapun di filesystem, melainkan memori virtual RAM murni yang diinisialisasi ke nilai 0.
5. **Kapan Arena Allocator menjadi pilihan alokasi yang buruk?**
   - *Jawaban*: Ketika siklus hidup objek acak dan program membutuhkan pembebasan memori satu per satu (*individual deallocation*) sepanjang program berjalan terus-menerus.

#### Bagian B: Intermediate Concepts (5 Soal)
6. **Apa dampak performa dari *False Sharing* pada multi-threaded memory allocation?**
   - *Jawaban*: Dua thread yang berjalan di core terpisah memodifikasi data independen yang berada pada satu cache line yang sama (64 byte), menyebabkan cache line terus bergantian di-invalidasi via Cache Coherency Protocol (MESI), melumpuhkan performa memori.
7. **Jelaskan perbedaan mendasar metadata chunk antara `ptmalloc` dan Pool Allocator kita!**
   - *Jawaban*: `ptmalloc` meletakkan ukuran dan flag di dalam memori kontigu user secara in-band pada setiap alokasi, sedangkan Pool Allocator memisahkan payload, memanfaatkan intrusive pointer untuk free chunks, dan menstandarisasi ukuran sehingga tidak perlu menyimpan field `size` per chunk.
8. **Bagaimana cara mendeteksi heap buffer overflow tanpa menggunakan Valgrind?**
   - *Jawaban*: Menggunakan mekanisme *canary pattern* yang diletakkan di batas memori alokasi (redzone), lalu memverifikasi nilainya saat dealokasi; atau mengompilasi program menggunakan `-fsanitize=address`.
9. **Mengapa `aligned_alloc(alignment, size)` standar C11 mengharuskan `size` bernilai kelipatan dari `alignment`?**
   - *Jawaban*: Standar C11 menetapkan aturan tersebut untuk memastikan array kontigu dari objek tersebut mempertahankan alignment yang konsisten pada setiap elemen tanpa *unaligned padding offset* tak terduga.
10. **Apa perbedaan antara alokasi Virtual Memory Address Space dan Resident Memory (RSS)?**
    - *Jawaban*: Virtual Address Space adalah reservasi pemetaan alamat logika oleh OS, sedangkan Resident Memory (RSS) adalah halaman fisik RAM yang benar-benar telah dipetakan oleh kernel akibat adanya operasi penulisan/pembacaan (Page Fault handling).

#### Bagian C: Skenario Kasus Produksi (3 Soal)

11. **Skenario 1**: Sebuah microservice written in C mengalami konsumsi RSS memory yang membengkak hingga puluhan gigabyte di production setelah berjalan 7 hari, padahal monitoring objek aktif aplikasi menunjukkan penggunaan konstan di angka 1.5GB. Analisis penyebabnya dan tentukan solusinya!
    - *Solusi & Analisis*: Ini adalah kasus klasik **External Fragmentation** pada alokator glibc (`ptmalloc`). Objek jangka panjang mengunci page memori virtual sehingga glibc tidak bisa melepaskannya kembali ke kernel via `madvise`/`brk`. Solusinya adalah memigrasikan alokasi objek kecil dengan frekuensi tinggi ke *Fixed-Size Pool Allocator*, memanggil `malloc_trim(0)` secara berkala, atau mengganti allocator ke `jemalloc` dengan tuning decay time agresif (`MALLOC_CONF="dirty_decay_ms:1000,muzzy_decay_ms:1000"`).

12. **Skenario 2**: Anda menjalankan profiler `perf` pada server jaringan berkecepatan tinggi dan menemukan bahwa 45% CPU cycles dihabiskan pada instruksi spinlock di dalam fungsi `_int_malloc` glibc. Perubahan arsitektur apa yang harus Anda lakukan?
    - *Solusi & Analisis*: Terjadi **Lock Contention** hebat karena puluhan thread pekerja berebut alokasi memori secara konkuren. Solusinya adalah mengadopsi arsitektur *Thread-Caching Suballocator* di mana masing-masing thread memiliki pool thread-local storage (`__thread`) independen yang telah dialokasikan di awal (zero contention), serta menukar transport komunikasi data antar thread menggunakan lock-free SPSC RingBuffer.

13. **Skenario 3**: Sebuah implementasi alokator custom mengalami segmentation fault sporadis di lingkungan ARM64 Cortex-A78, padahal berjalan tanpa crash di arsitektur x86-64. Apa potensi penyebab pada level arsitektur hardware?
    - *Solusi & Analisis*: Penyebab utamanya adalah **Unaligned Memory Access**. CPU x86-64 secara hardware memaafkan unaligned memory access (dengan sedikit penalti performa), namun sebagian arsitektur prosesor ARM secara ketat memicu pengecualian hardware (*alignment fault trap*) ketika pointer tipe multi-byte (seperti pointer atau instruksi vektor NEON/SIMD) mengakses alamat memori yang tidak habis dibagi oleh nilai lebar byte tipenya. Solusinya adalah mengevaluasi formula bitwise alignment padding dan memastikan semua chunk mematuhi batas alignment minimal `max_align_t` atau 64-byte.

---

### 16. Summary

* Alokator memori standar bersifat serbaguna namun membawa overhead metadata in-band, potensi fragmentasi eksternal, dan risiko *lock contention* pada sistem multi-core berskala enterprise.
* Pemilihan subalokator yang tepat merupakan pilar fundamental dalam rekayasa perangkat lunak sistem performa tinggi:
  - **Arena Allocator** mengorbankan granularitas dealokasi untuk mendapatkan kecepatan maksimum dan zero external fragmentation.
  - **Pool/Slab Allocator** memberikan kecepatan alokasi/dealokasi $\mathcal{O}(1)$ deterministik bagi objek seragam dengan memanfaatkan teknik *intrusive linked list*.
* Desain arsitektur memori modern wajib memperhitungkan layout perangkat keras: batas cache line (64 byte) harus selalu dihormati untuk memaksimalkan transfer *L1 cache burst*, mengeliminasi *unaligned access penalties*, dan memitigasi *false sharing*.
* Sistem produksi kelas industri wajib dilengkapi instrumen observabilitas memori, mulai dari canary integrity check, proteksi isolasi mmap, hingga sanitasi otomatis saat runtime.