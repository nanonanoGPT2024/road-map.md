# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Pointer Mastery, Aritmetika Alamat, dan Manipulasi Memori Tingkat Rendah**
**Kategori: 02-Programming-Languages / C**

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengonstruksi model mental arsitektur memori fisik dan virtual (MMU, TLB, Cache Lines, Paging) serta korelasinya dengan manipulasi pointer C standar C11/C17/C23.
- Menguasai *pointer arithmetic* tingkat lanjut secara deterministik pada level *byte-offset* dengan mematuhi batasan *pointer provenance* dan standar ISO/IEC 9899.
- Mengimplementasikan teknik manipulasi memori performa tinggi (*type punning*, *unaligned memory access handling*, *strict aliasing compliance* dengan `memcpy` dan union).
- Mengeliminasi *undefined behavior* (UB) akibat pelanggaran *strict aliasing rule*, *pointer overflow*, dan *out-of-bounds provenance*.
- Mendesain dan membangun subsistem alokasi memori kustom kelas enterprise (*Arena Allocator*, *Slab/Pool Allocator*) untuk infrastruktur sistem dengan latensi sub-mikrodetik tanpa alokasi dinamis `malloc`/`free` di *hot path*.

---

## 2. Prerequisites
- Pemahaman solid tentang variabel primitif, struktur kontrol, dan fungsi dalam C.
- Memahami dasar pointer level 1: Deklarasi `int *p`, operator dereferensi `*`, dan operator alamat `&`.
- Pemahaman representasi data biner (Two's Complement, Endianness: Little vs Big Endian, Bitwise Operators).
- Pengalaman dasar menggunakan *tooling* GNU Toolchain (GCC/Clang) dan sistem operasi POSIX (Linux).

---

## 3. Concept & Internal Architecture

### 3.1 Virtual Memory, Paging, dan Translation Lookaside Buffer (TLB)
Pointer dalam C modern pada sistem operasi dengan MMU (*Memory Management Unit*) bukan alamat fisik (Physical Address), melainkan **Virtual Address**. 

```
+-------------------------------------------------------------------+
|                     64-bit Virtual Address                        |
|   +-------------------+--------------------+--------------------+ |
|   | Page Directory Idx| Page Table Entry   |   Offset (12-bit)  | |
|   +-------------------+--------------------+--------------------+ |
+-------------------------------------------------------------------+
                                  |
                                  v
                       [ MMU / TLB Lookup ]
                                  |
                                  v
               +--------------------------------------+
               | Physical Frame Base + Offset (4 KiB) |
               +--------------------------------------+
```

Ketika aplikasi mendereferensikan sebuah pointer:
1. CPU mengevaluasi Virtual Address ke TLB (*L1/L2 Translation Lookaside Buffer*).
2. Jika terjadi *TLB Miss*, CPU melakukan *page table walk* di memori fisik melalui register `CR3` (pada arsitektur x86_64).
3. Jika halaman tidak valid atau tidak dipetakan dengan izin akses yang tepat (Read/Write/Execute), interrupt perangkat keras dibangkitkan: CPU memicu Exception 14 (*Page Fault*), yang oleh kernel Linux diterjemahkan menjadi sinyal `SIGSEGV` (*Segmentation Fault*).

### 3.2 Cache Lines, Spatial Locality, dan Hardware Alignment
CPU tidak pernah membaca atau menulis satu bita tunggal dari RAM; data ditransfer dalam satuan **Cache Line** (umumnya 64 byte pada arsitektur modern x86_64 dan ARM64).
- **Spatial Locality**: Mengakses memori secara sekuensial (stride-1) memanfaatkan prefetcher perangkat keras L1/L2. Pointer arithmetic acak melintasi batas 64-byte menyebabkan *Cache Miss* yang mengorbankan 150-250 *cycle* CPU per akses.
- **Natural Alignment**: Tipe data dengan ukuran $N$ byte harus dialokasikan pada alamat memori yang merupakan kelipatan dari $N$ (`address % sizeof(T) == 0`).
  - `uint32_t` (4 byte) harus berada di alamat kelipatan 4.
  - `uint64_t` / Pointer (8 byte) harus berada di alamat kelipatan 8.
- **Unaligned Access Penalty**: Pada arsitektur x86, akses tidak selaras (*unaligned*) ditoleransi oleh CPU dengan penalti performa (atau split lock jika melintasi batas cache line). Pada beberapa arsitektur RISC (ARM lawas, MIPS), akses tidak selaras langsung memicu instruksi *Bus Error* (`SIGBUS`).

### 3.3 Pointer Provenance dan Aturan Strict Aliasing
Standar C (ISO/IEC 9899) mendefinisikan objek memori bukan sekadar blok bita mentah, melainkan entitas yang memiliki **Provenance** (asal-usul alokasi).
- Dua pointer tidak boleh diasumsikan menunjuk ke blok memori yang sama jika berasal dari alokasi yang berbeda, meskipun alamat numeriknya kebetulan bersinggungan secara teoretis setelah manipulasi integer casting.
- **Strict Aliasing Rule (C11 §6.5/7)**: Kompiler mengasumsikan pointer dari tipe yang berbeda tidak menunjuk ke lokasi memori yang sama.
  ```c
  void process(uint32_t *a, float *b) {
      *a = 10;
      *b = 5.0f;
      // Kompiler berhak mengasumsikan *a MASIH 10, 
      // mengabaikan kemungkinan 'a' dan 'b' menunjuk memori yang sama!
  }
  ```
- **Pengecualian Karakter**: `char*`, `signed char*`, `unsigned char*`, dan `uint8_t` secara eksplisit diizinkan melakukan *aliasing* ke tipe objek apa pun untuk inspeksi bita mentah.

---

## 4. Why & What

### Mengapa Pointer Mastery Wajib untuk Skala Enterprise?
Pada sistem skala enterprise (Database Engine, Jaringan Telekomunikasi L4-L7, High-Frequency Trading, Operating System Kernels):
1. **Zero-Copy Architecture**: Memindahkan *payload* sebesar 10 GiB/detik tidak dapat dilakukan menggunakan penyalinan data *by-value*. Satu-satunya solusi adalah menggeser kepemilikan pointer melalui *ring buffer*.
2. **Deterministic Latency**: Menghindari *latency spikes* dari `malloc()` yang bergantung pada internal heap lock glibc (`ptmalloc`) dan sistem defragmentasi kernel.
3. **Hardware Interfacing**: Pemetaan register perangkat keras (*Memory-Mapped I/O* - MMIO) dan struktur paket jaringan biner mensyaratkan inspeksi memori level bita secara presisi.

### Apa itu Pointer Sebenarnya?
Pointer adalah tipe data skalar yang nilainya diinterpretasikan sebagai alamat dalam ruang alamat virtual mesin. Operasi aritmetika pada pointer (`ptr + n`) secara otomatis diskalakan dengan ukuran objek yang ditunjuk:
$$\text{Effective Address} = \text{Address} + (n \times \text{sizeof}(*ptr))$$

---

## 5. How: Workflow Manipulasi Memori & Siklus Hidup Alokasi

```
           +---------------------------------------------+
           |       1. Akuisisi Virtual Memory            |
           |  (OS: mmap() / posix_memalign / Heap Pool)  |
           +---------------------------------------------+
                                  |
                                  v
           +---------------------------------------------+
           |       2. Verifikasi Batas Alignment         |
           |      ((uintptr_t)ptr & (align - 1)) == 0    |
           +---------------------------------------------+
                                  |
                                  v
           +---------------------------------------------+
           |      3. Partisi Memori (Pointer Bump)       |
           |    current = base + offset; offset += sz    |
           +---------------------------------------------+
                                  |
                                  v
           +---------------------------------------------+
           |        4. Akses Memori Aman & Akselerasi    |
           |  (Mematuhi Strict Aliasing & Bounds Check)  |
           +---------------------------------------------+
                                  |
                                  v
           +---------------------------------------------+
           |       5. Reset Batch / Reclaim Total        |
           |      (Zeroing Overhead, O(1) Lifetime)      |
           +---------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Apartemen Bertingkat dan Penomoran Kamar
Bayangkan sebuah hotel korporat super besar:
- Alamat kamar (`uintptr_t`) adalah nomor pintu absolut (misal: 1024).
- Tipe pointer mendikte ukuran kamar:
  - `char *`: Setiap kamar hanya berukuran 1 kasur kecil (1 byte). Melangkah `ptr + 1` memindahkan Anda tepat ke pintu 1025.
  - `int64_t *`: Setiap kamar adalah *penthouse* yang mencakup 8 nomor pintu (8 byte). Melangkah `ptr + 1` memindahkan Anda dari pintu 1024 langsung ke pintu 1032.
- **Strict Aliasing Rule Violation**: Mengasumsikan bahwa kunci untuk kamar tidur VIP (`float*`) bisa membuka kotak brankas industri (`uint64_t*`) di nomor pintu yang sama tanpa renovasi resmi (`memcpy`), menyebabkan sistem keamanan hotel (*kompiler optimizer*) membuat asumsi yang keliru dan merusak barang-barang Anda.

```
Array of struct Data { int32_t id; char tag; /* 3 padding */ float val; };
Ukuran: 12 byte (karena natural alignment float 4 byte)

Memori Fisik (Byte):
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
|  id_0  |  id_1  |  id_2  |  id_3  |  tag   |  PAD   |  PAD   |  PAD   | val_0  | val_1  | val_2  | val_3  |
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
|<- - - - - - - int32_t (4B) - - - ->|<-char->|<- - - - PADDING - - - ->|<- - - - - float (4B) - - - - ->|
^
|-- Base Pointer: ptr
|-- Pointer Arithmetic: ((char*)ptr) + 8  --> Menunjuk langsung ke alamat val
|-- JANGAN: ((float*)(ptr + 1))           --> ERROR! Skala melompat 12 byte, bukan 8!
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Pointer Arithmetic & Type Casting Fundamentals
Program ini mengilustrasikan perbedaan kalkulasi aritmetika pada berbagai jenis pointer dan manipulasi bita aman.

```c
#include <stdio.h>
#include <stdint.h>
#include <inttypes.h>

int main(void) {
    uint32_t raw_buffer[4] = {0x11223344, 0x55667788, 0x99AABBCC, 0xDDEEFF00};
    
    uint32_t *p32 = raw_buffer;
    printf("[*] Base Address p32          : %p\n", (void*)p32);
    printf("[*] Address p32 + 1           : %p (Diff: %td bytes)\n", 
           (void*)(p32 + 1), (char*)(p32 + 1) - (char*)p32);

    // Casting ke pointer bita mentah (uint8_t)
    uint8_t *p8 = (uint8_t*)raw_buffer;
    printf("[*] Address p8 + 1            : %p (Diff: %td byte)\n", 
           (void*)(p8 + 1), (char*)(p8 + 1) - (char*)p8);

    // Inspeksi byte individual (Little-Endian Verification)
    printf("[*] Byte at offset 0          : 0x%02X\n", *p8);
    printf("[*] Byte at offset 1          : 0x%02X\n", *(p8 + 1));

    // Pointer Difference (ptrdiff_t)
    uint32_t *end = &raw_buffer[3];
    ptrdiff_t elements = end - p32;
    printf("[*] Elements count (end - p32): %td\n", elements);

    return 0;
}
```

### 7.2 Practical Example: Arena Memory Allocator (Production Grade)
Arena Allocator mengeliminasi overhead *per-allocation lock* dan fragmentasi memori, standar untuk sistem *game engine* dan *high-frequency order book processing*.

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>

#define DEFAULT_ALIGNMENT (sizeof(void*))

typedef struct {
    uint8_t *buffer;
    size_t   capacity;
    size_t   offset;
} Arena;

static inline bool is_power_of_two(uintptr_t x) {
    return (x & (x - 1)) == 0;
}

static inline uintptr_t align_forward(uintptr_t ptr, size_t alignment) {
    assert(is_power_of_two(alignment));
    uintptr_t p = ptr;
    uintptr_t a = (uintptr_t)alignment;
    uintptr_t modulo = p & (a - 1);
    
    if (modulo != 0) {
        p += (a - modulo);
    }
    return p;
}

Arena arena_create(size_t capacity) {
    Arena arena = {0};
    arena.buffer = (uint8_t*)malloc(capacity);
    if (arena.buffer) {
        arena.capacity = capacity;
        arena.offset = 0;
    }
    return arena;
}

void* arena_alloc_align(Arena *arena, size_t size, size_t alignment) {
    uintptr_t current_ptr = (uintptr_t)arena->buffer + arena->offset;
    uintptr_t aligned_ptr = align_forward(current_ptr, alignment);
    
    size_t new_offset = (aligned_ptr - (uintptr_t)arena->buffer) + size;

    if (new_offset > arena->capacity) {
        // Out of memory dalam arena
        return NULL;
    }

    arena->offset = new_offset;
    return (void*)aligned_ptr;
}

void* arena_alloc(Arena *arena, size_t size) {
    return arena_alloc_align(arena, size, DEFAULT_ALIGNMENT);
}

void arena_reset(Arena *arena) {
    arena->offset = 0;
}

void arena_destroy(Arena *arena) {
    free(arena->buffer);
    arena->buffer = NULL;
    arena->capacity = 0;
    arena->offset = 0;
}

typedef struct {
    int32_t session_id;
    double  timestamp;
    char    payload[17];
} TelemetryPacket;

int main(void) {
    Arena memory_arena = arena_create(1024 * 1024); // Alokasi pre-allocated 1 MiB
    if (!memory_arena.buffer) {
        fprintf(stderr, "Failed to initialize Arena\n");
        return 1;
    }

    printf("[Arena] Base Address: %p\n", (void*)memory_arena.buffer);

    // Alokasi 1000 struct TelemetryPacket dengan jaminan alignment
    TelemetryPacket *packet = (TelemetryPacket*)arena_alloc(&memory_arena, sizeof(TelemetryPacket));
    if (!packet) {
        fprintf(stderr, "Allocation failed!\n");
        return 1;
    }
    packet->session_id = 998244353;
    packet->timestamp = 1711929600.12345;
    strncpy(packet->payload, "METRIC_HEARTBEAT", sizeof(packet->payload) - 1);

    printf("[Arena] Packet Allocated at: %p (Offset: %zu)\n", (void*)packet, memory_arena.offset);
    printf("[Arena] Alignment Check: %s\n", 
           ((uintptr_t)packet % _Alignof(TelemetryPacket) == 0) ? "ALIGNED" : "UNALIGNED");

    // Alokasi kedua: Buffer mentah byte
    uint8_t *raw_stream = (uint8_t*)arena_alloc(&memory_arena, 256);
    printf("[Arena] Raw Stream Allocated at: %p (Offset: %zu)\n", (void*)raw_stream, memory_arena.offset);

    // O(1) Bulk Free
    arena_reset(&memory_arena);
    printf("[Arena] Reset done. Current offset: %zu\n", memory_arena.offset);

    arena_destroy(&memory_arena);
    return 0;
}
```

---

## 8. Real World Case Study: High-Throughput Network Ring Buffer

### Masalah
Sebuah mesin L4 Reverse Proxy menerima jutaan paket UDP DNS per detik. Menggunakan alokasi standar `malloc()` dan `free()` per-paket menghasilkan latensi tail p99 di atas 15 milidetik karena *thread contention* pada metadata heap glibc dan fragmentasi virtual memory (*memory bloat*).

### Solusi Arsitektur
Membangun **Single-Producer Single-Consumer (SPSC) Cache-Aligned Lock-Free Ring Buffer** yang memanfaatkan manipulasi pointer circular, zero-copy read/write, dan *cache padding* untuk menghindari *false sharing*.

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <string.h>

#define CACHE_LINE_SIZE 64
#define RING_BUFFER_CAPACITY 1024 // Wajib bernilai 2^N

typedef struct {
    uint32_t packet_id;
    uint32_t length;
    uint8_t  payload[512];
} NetworkPacket;

typedef struct {
    // Producer Cache Line
    _Alignas(CACHE_LINE_SIZE) _Atomic size_t head;
    
    // Consumer Cache Line (Terisolasi dari Head untuk mencegah False Sharing)
    _Alignas(CACHE_LINE_SIZE) _Atomic size_t tail;

    // Buffer Data Storage
    _Alignas(CACHE_LINE_SIZE) NetworkPacket storage[RING_BUFFER_CAPACITY];
} SPSCRingBuffer;

SPSCRingBuffer* ring_buffer_create(void) {
    SPSCRingBuffer *rb = NULL;
    // Mengalokasikan memori selaras dengan batas cache line 64-byte
    if (posix_memalign((void**)&rb, CACHE_LINE_SIZE, sizeof(SPSCRingBuffer)) != 0) {
        return NULL;
    }
    atomic_init(&rb->head, 0);
    atomic_init(&rb->tail, 0);
    return rb;
}

bool ring_buffer_enqueue(SPSCRingBuffer *rb, const NetworkPacket *src) {
    size_t current_head = atomic_load_explicit(&rb->head, memory_order_relaxed);
    size_t current_tail = atomic_load_explicit(&rb->tail, memory_order_acquire);

    if ((current_head - current_tail) >= RING_BUFFER_CAPACITY) {
        // Buffer Penuh
        return false;
    }

    // Hitung offset menggunakan bitwise mask (Substitusi operasi modulo % yang lambat)
    size_t index = current_head & (RING_BUFFER_CAPACITY - 1);
    
    // Direct pointer dereference copy
    memcpy(&rb->storage[index], src, sizeof(NetworkPacket));

    atomic_store_explicit(&rb->head, current_head + 1, memory_order_release);
    return true;
}

bool ring_buffer_dequeue(SPSCRingBuffer *rb, NetworkPacket *dest) {
    size_t current_tail = atomic_load_explicit(&rb->tail, memory_order_relaxed);
    size_t current_head = atomic_load_explicit(&rb->head, memory_order_acquire);

    if (current_tail == current_head) {
        // Buffer Kosong
        return false;
    }

    size_t index = current_tail & (RING_BUFFER_CAPACITY - 1);
    memcpy(dest, &rb->storage[index], sizeof(NetworkPacket));

    atomic_store_explicit(&rb->tail, current_tail + 1, memory_order_release);
    return true;
}

int main(void) {
    SPSCRingBuffer *rb = ring_buffer_create();
    if (!rb) {
        perror("posix_memalign");
        return 1;
    }

    printf("[RingBuffer] Init at address: %p\n", (void*)rb);
    printf("[RingBuffer] Head Address   : %p\n", (void*)&rb->head);
    printf("[RingBuffer] Tail Address   : %p (Delta: %td bytes)\n", 
           (void*)&rb->tail, (uintptr_t)&rb->tail - (uintptr_t)&rb->head);

    NetworkPacket pkt_in = {
        .packet_id = 1001,
        .length = 4,
        .payload = {0xDE, 0xAD, 0xBE, 0xEF}
    };

    if (ring_buffer_enqueue(rb, &pkt_in)) {
        printf("[RingBuffer] Packet %u Enqueued successfully\n", pkt_in.packet_id);
    }

    NetworkPacket pkt_out;
    if (ring_buffer_dequeue(rb, &pkt_out)) {
        printf("[RingBuffer] Packet %u Dequeued: Payload[0]=0x%X\n", 
               pkt_out.packet_id, pkt_out.payload[0]);
    }

    free(rb);
    return 0;
}
```

---

## 9. Trade-offs

| Parameter Arsitektur | Pointer Dereferensi Standar (`malloc`/`free`) | Custom Arena Allocator | Ring Buffer Zero-Copy |
| :--- | :--- | :--- | :--- |
| **Alokasi Latensi** | $O(\log N)$ s.d. $O(N)$ (Bergantung fragmentasi & lock contention) | $O(1)$ Deterministic (Hanya manipulasi pointer integer) | $O(1)$ Deterministic (Sub-mikrodetik, lockless) |
| **Overhead Metadata**| 8–16 byte per alokasi (glibc chunk header) | 0 byte per alokasi individual (Hanya metadata Arena) | 0 byte per item (Ukuran fixed array) |
| **Deallocation Granularity** | Per-objek fleksibel | Seluruh arena sekaligus (Bulk reclamation) | FIFO queue order deterministik |
| **Safety Risk** | *Use-after-free*, *Double free*, *Memory leak* | Memory leak jika lifecycle batch salah dihitung | Overwrite jika kapasitas under-provisioned |
| **Cache Miss Ratio** | Tinggi (Memori tersebar di virtual address space) | Sangat Rendah (Data sequential, spatial locality tinggi) | Minimal (Data berputar di baris cache yang panas) |

---

## 10. Common Mistakes & Troubleshooting

### 1. Pelanggaran Strict Aliasing melalui Raw Pointer Casting
*Anti-Pattern:*
```c
// BAHAYA: Mengakses float melalui pointer int32_t melanggar standar C
float f = 5.25f;
int32_t *p = (int32_t*)&f; 
printf("Bits: %x\n", *p); // UNDEFINED BEHAVIOR: Kompiler dapat mengoptimasi secara agresif
```
*Solusi Terstandarisasi:*
```c
// Solusi 1: Gunakan memcpy (Dikenali kompiler dan dioptimasi jadi single assembly instruction: movd / mov)
float f = 5.25f;
int32_t bits;
memcpy(&bits, &f, sizeof(bits));

// Solusi 2: Gunakan Type Punning via Union (Resmi legal di standar C99/C11/C17 §6.5.2.3)
union {
    float f;
    int32_t i;
} pun;
pun.f = 5.25f;
printf("Bits: %x\n", pun.i);
```

### 2. Pointer Arithmetic pada Pointer `void*`
Standar ANSI/ISO C melarang operasi matematika langsung pada pointer `void*` karena `void` tidak memiliki ukuran (`sizeof(void)` adalah ekspresi ilegal). Walaupun GCC mengizinkannya via ekstensi GNU (menganggap `sizeof(void) == 1`), kode tersebut **tidak portabel**.
```c
void *data = get_buffer();
// data = data + 16; // NON-PORTABLE COMPILER ERROR (MSVC / Strict Clang)
uint8_t *safe_data = (uint8_t*)data;
safe_data += 16;     // BENAR & PORTABEL
```

### 3. Pointer Provenance & Relational Comparison Bugs
Membandingkan dua pointer dengan operator `<`, `<=`, `>`, `>=` yang tidak menunjuk pada array atau objek yang sama adalah **Undefined Behavior (C11 §6.5.8)**.
```c
int a = 10;
int b = 20;
if (&a < &b) { // UNDEFINED BEHAVIOR: &a dan &b berasal dari alokasi terpisah di stack!
    // Kompiler berhak menganggap ekspresi ini dead code atau selalu false
}
```

### Panduan Debugging dengan Sanitizer
Gunakan tool modern untuk mendeteksi kerusakan pointer secara instan pada waktu eksekusi:
```bash
# Kompilasi dengan AddressSanitizer dan UndefinedBehaviorSanitizer
gcc -std=c11 -Wall -Wextra -fsanitize=address,undefined -g -O1 main.c -o main_sanitized
./main_sanitized
```

---

## 11. Best Practices (Production Checklist)

1. [ ] **Explicit Pointer Types**: Hindari transmisi pointer generik tanpa membungkusnya dalam *opaque pointer structure* (`typedef struct Context Context;`).
2. [ ] **Cast via Byte Types**: Selalu cast ke `uint8_t*` atau `char*` sebelum melakukan offset bita manual.
3. [ ] **Verifikasi Alignment Objek**: Selalu pastikan pointer alamat memenuhi batasan kelipatan target:
   `assert(((uintptr_t)ptr % _Alignof(TargetType)) == 0);`
4. [ ] **Aktifkan Flag Strict Checking**: Sertakan `-Wall -Wextra -Wstrict-aliasing=2 -pedantic` pada build toolchain pipeline Anda.
5. [ ] **Gunakan `restrict` Keyword**: Berikan petunjuk ke kompiler bahwa dua pointer tidak saling bertindih (*aliasing*) untuk memungkinkan optimasi SIMD auto-vectorization:
   ```c
   void add_arrays(size_t n, int * restrict a, const int * restrict b) {
       for (size_t i = 0; i < n; i++) a[i] += b[i];
   }
   ```
6. [ ] **Zeroized Invalidation**: Setel pointer ke `NULL` segera setelah pembebasan (*dangling pointer mitigation*).

---

## 12. Hands-on Practice: Membangun Typed Fixed-Block Pool Allocator

Buat direktori latihan:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### File: `hands-on/m02/pool_allocator.c`
Tuliskan implementasi *Pool Allocator* modular berikut yang memanfaatkan teknik *embedded free-list* (pointer ke blok bebas berikutnya disimpan langsung di dalam blok yang sedang tidak terpakai tanpa overhead memori tambahan).

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>

typedef struct FreeNode {
    struct FreeNode *next;
} FreeNode;

typedef struct {
    uint8_t *raw_memory;
    size_t   block_size;
    size_t   capacity;
    FreeNode *free_list_head;
} FixedPool;

FixedPool* pool_create(size_t block_size, size_t capacity, size_t alignment) {
    assert(block_size >= sizeof(FreeNode) && "Block size must accommodate metadata");
    
    FixedPool *pool = (FixedPool*)malloc(sizeof(FixedPool));
    if (!pool) return NULL;

    pool->block_size = block_size;
    pool->capacity = capacity;

    size_t total_size = block_size * capacity;
    if (posix_memalign((void**)&pool->raw_memory, alignment, total_size) != 0) {
        free(pool);
        return NULL;
    }

    // Bangun In-Place Linked Free-List via Pointer Arithmetic
    pool->free_list_head = (FreeNode*)pool->raw_memory;
    FreeNode *curr = pool->free_list_head;

    for (size_t i = 0; i < capacity - 1; i++) {
        uintptr_t next_addr = (uintptr_t)curr + block_size;
        curr->next = (FreeNode*)next_addr;
        curr = curr->next;
    }
    curr->next = NULL; // Node terakhir menunjuk NULL

    return pool;
}

void* pool_alloc(FixedPool *pool) {
    if (pool->free_list_head == NULL) {
        return NULL; // Out of memory dalam pool
    }

    // Ambil node terdepan (O(1))
    FreeNode *node = pool->free_list_head;
    pool->free_list_head = node->next;

    return (void*)node;
}

void pool_free(FixedPool *pool, void *ptr) {
    if (!ptr) return;

    // Sanity check: Pastikan ptr berada dalam jangkauan alamat pool
    uintptr_t p = (uintptr_t)ptr;
    uintptr_t start = (uintptr_t)pool->raw_memory;
    uintptr_t end = start + (pool->block_size * pool->capacity);
    assert(p >= start && p < end && "Pointer does not belong to this pool!");

    // Kembalikan node ke linked-list free (O(1))
    FreeNode *node = (FreeNode*)ptr;
    node->next = pool->free_list_head;
    pool->free_list_head = node;
}

void pool_destroy(FixedPool *pool) {
    if (pool) {
        free(pool->raw_memory);
        free(pool);
    }
}

int main(void) {
    printf("[*] Inisialisasi Memory Pool Allocator...\n");
    FixedPool *pool = pool_create(64, 4, 64);
    assert(pool != NULL);

    printf("[*] Mengalokasikan 4 blok...\n");
    void *b1 = pool_alloc(pool);
    void *b2 = pool_alloc(pool);
    void *b3 = pool_alloc(pool);
    void *b4 = pool_alloc(pool);

    printf("  Block 1: %p\n", b1);
    printf("  Block 2: %p (Diff: %td)\n", b2, (char*)b2 - (char*)b1);
    printf("  Block 3: %p\n", b3);
    printf("  Block 4: %p\n", b4);

    void *b_fail = pool_alloc(pool);
    printf("[*] Alokasi ke-5 (Harus NULL): %p\n", b_fail);

    printf("[*] Membebaskan Block 2 (%p)...\n", b2);
    pool_free(pool, b2);

    void *b_reused = pool_alloc(pool);
    printf("[*] Alokasi baru setelah free: %p (Harus sama dengan Block 2)\n", b_reused);
    assert(b_reused == b2);

    pool_destroy(pool);
    printf("[*] Eksekusi hands-on sukses tanpa memory leak.\n");
    return 0;
}
```

### Langkah Kompilasi & Verifikasi:
```bash
gcc -std=c11 -Wall -Wextra -Werror -fsanitize=address pool_allocator.c -o pool_test
./pool_test
```

---

## 13. Exercise

### Level Easy
Tuliskan fungsi C bernama `void swap_endian32(uint32_t *val)` yang menerima pointer ke `uint32_t`, membedah representasi bita menggunakan pointer `uint8_t*`, dan menukar urutan bita secara in-place sehingga Little-Endian berubah menjadi Big-Endian atau sebaliknya.
- **Kriteria Evaluasi**: Dilarang menggunakan fungsi pustaka bawaan seperti `htonl`/`ntohl`. Harus murni menggunakan dereferensi aritmetika pointer bita.

### Level Medium
Implementasikan fungsi `void* custom_memset_aligned(void *dst, int val, size_t size)`.
- **Kriteria Evaluasi**: Fungsi harus mengisi memori bita per bita menggunakan `uint8_t*` hingga pointer mencapai *8-byte aligned address*. Setelah selaras, fungsi harus memproses blok memori menggunakan pointer `uint64_t*` (8 byte per siklus iterasi loop). Sisa bita yang tidak habis dibagi 8 harus diselesaikan menggunakan `uint8_t*`.

### Level Hard
Rancang struktur data **Circular Buffer Multi-Tier Pointers** (`void ***buffer_matrix`) yang mengalokasikan matriks dimensi ganda menggunakan alokasi satu kali panggilan (*single contiguous memory chunk*). 
- **Kriteria Evaluasi**: Seluruh baris dan pointer matriks harus berada dalam 1 blok memori linear. Tidak boleh ada pemanggilan alokasi berulang dalam loop. Implementasikan fungsi pelepasan (`matrix_free`) yang hanya memerlukan satu instruksi `free()`.

---

## 14. Challenge: Zero-Copy Network Frame Serializer Engine
Sebuah kartu antarmuka jaringan kecepatan tinggi (SmartNIC) mentransmisikan *packet frame* dengan protokol kustom biner. Paket tersebut memiliki header bervariasi (*Variable-Length Frame Header*):

```
[2-Byte Magic: 0x55AA] 
[1-Byte Operation Code] 
[1-Byte Reserved / Alignment Pad] 
[4-Byte Transaction ID] 
[2-Byte Payload Length (N)] 
[N-Byte Dynamic Binary Payload] 
[4-Byte Cyclic Redundancy Check (CRC32)]
```

### Tantangan:
Rancang dan implementasikan mesin parsing tanpa salinan bita (*Zero-Copy Deserializer Engine*):
1. Fungsi parsing menerima buffer mentah bita stream `const uint8_t *raw_stream, size_t total_len`.
2. Kembalikan representasi *view* paket menggunakan struktur C yang memetakan field-field tersebut secara *zero-copy* tanpa mengalokasikan heap baru.
3. Alamat field `Transaction ID` dan `CRC32` harus tetap aman diakses meskipun buffer yang diterima berada pada *unaligned byte stream* (misal offset dimulai dari ganjil).
4. Jika CPU Anda membutuhkan alignment, Anda harus mengisolasi pembacaan unaligned tersebut secara manual menggunakan manipulasi pointer bitwise shift deterministik.
5. Jalankan stress test dengan 1.000.000 frame biner acak di bawah AddressSanitizer. Nol kebocoran memori (*0 leaks*), nol kegagalan segmentasi (*0 faults*).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: 5 Pertanyaan Basic
1. Jika dideklarasikan `int16_t arr[4];`, berapakah nilai `(char*)(&arr[3]) - (char*)(&arr[0])`?
2. Apa bahaya melakukan dereferensi pointer `char*` yang baru saja di-*cast* langsung menjadi `double*` tanpa verifikasi keselarasan (*alignment*)?
3. Mengapa ekspresi `void *p; p++;` dianggap tidak valid pada standar C murni (ISO/IEC 9899)?
4. Berapa bita ruang yang dihabiskan oleh sebuah pointer pada arsitektur sistem operasi 64-bit modern (x86_64)?
5. Apa makna teknis dari spesifikasi tipe data `uintptr_t` dan apa perbedaannya dengan `size_t`?

### Bagian B: 5 Pertanyaan Intermediate
6. Jelaskan bagaimana kompiler memanfaatkan kata kunci `restrict` pada pointer argumen fungsi untuk mengoptimalkan kode mesin perakitan (*assembly*)!
7. Diberikan kode berikut:
   ```c
   int a = 42;
   void *vp = &a;
   *(int*)vp = 84;
   ```
   Apakah kode ini melanggar *Strict Aliasing Rule*? Jelaskan alasan standarnya!
8. Pada sistem x86_64 dengan *cache line* 64 bita, apa implikasi struktural jika sebuah struct 64-byte diletakkan di alamat memori `0x103E`?
9. Jelaskan mengapa mengalokasikan memori menggunakan pola *Bump/Arena Allocator* dapat meningkatkan performa secara signifikan dibandingkan alokasi berulang via `malloc()`!
10. Apa yang dimaksud dengan *Pointer Provenance* dan mengapa perbandingan pointer `ptr1 < ptr2` adalah UB jika keduanya bukan anggota array yang sama?

### Bagian C: 3 Skenario Kasus Produksi
11. **Skenario 1**: Aplikasi backend server crash mendadak dengan sinyal `SIGBUS` saat dijalankan di server berbasis ARM64, padahal pada mesin dev lokal x86_64 berjalan 100% mulus. Berdasarkan arsitektur pointer dan memori, apa akar masalahnya dan bagaimana menelusurinya?
12. **Skenario 2**: Sistem telemetri IoT memproses jutaan event dengan memetakan struct langsung ke buffer network:
    ```c
    Header *hdr = (Header*)network_rx_buffer;
    ```
    Kompilasi dengan `-O0` berjalan lancar, namun ketika dinaikkan ke `-O3` data corrupted secara acak. Jelaskan apa yang terjadi di level optimasi kompiler!
13. **Skenario 3**: Dua thread pada sistem *multi-core* sering memodifikasi dua pointer berbeda: `Thread A` memodifikasi `ptr_a` dan `Thread B` memodifikasi `ptr_b`. Meskipun kedua pointer independen, performa drop drastis hingga 80%. Masalah pointer/arsitektur perangkat keras apa yang sedang terjadi?

---

### Kunci Jawaban & Solusi Quiz

#### Solusi Bagian A: Basic
1. **6 bita**. Tiap elemen `int16_t` berukuran 2 bita. Indeks 3 berjarak 3 elemen dari indeks 0. $3 \times 2 = 6$ bita. Karena di-cast ke `char*`, aritmetika menghitung selisih bita mentah.
2. Berpotensi memicu **Unaligned Access Crash** (`SIGBUS`) pada arsitektur strict-alignment (seperti SPARC, MIPS, atau ARM model tertentu), atau degradasi performa drastis akibat split-cache reading pada arsitektur x86.
3. Tipe `void` adalah tipe tak lengkap (*incomplete type*) yang tidak memiliki ukuran definisi (`sizeof(void)` tidak ada menurut standar). Kompiler tidak dapat menghitung offset penambahan alamat.
4. **8 byte (64 bit)**, independen dari tipe data objek yang ditunjuk oleh pointer tersebut.
5. `uintptr_t` adalah tipe integer unsigned yang dijamin memiliki lebar bit yang mampu menampung representasi utuh dari sebuah pointer void (`void*`) tanpa pemotongan data. `size_t` adalah tipe integer unsigned representasi ukuran objek dalam memori.

#### Solusi Bagian B: Intermediate
6. `restrict` menjamin kepada kompiler bahwa selama masa hidup pointer tersebut, objek yang ditunjuknya **hanya** akan diakses melalui pointer itu (tidak dialiaskan oleh pointer lain). Hal ini memungkinkan kompiler menaruh nilai dalam register CPU dan memparalelkan eksekusi via SIMD register tanpa perlu memuat ulang data dari cache/RAM secara berulang.
7. **Tidak melanggar**. Standar C secara eksplisit memperbolehkan casting ke `void*` dan mengembalikannya ke tipe aslinya (`int*`). *Strict Aliasing* hanya dilanggar jika mengakses memori bertipe $T_1$ menggunakan pointer bertipe $T_2$ yang tidak kompatibel.
8. Objek struct tersebut akan **melintasi batas cache line** (*Cache Line Boundary Crossing*). Alamat `0x103E` ditambah 64 byte jatuh pada `0x107E`. Hal ini menyebabkan satu operasi pembacaan struct harus mengeksekusi dua siklus pembacaan cache line (jalur `0x1000` dan `0x1040`), memicu fenomena *split load* yang merusak performa.
9. Karena Arena Allocator hanya melakukan operasi penjumlahan skalar integer sederhana (`offset += size`) pada contiguous virtual space yang sudah dialokasikan. Tidak ada heap graph search, tidak ada metadata header chunk splitting, dan data memiliki *spatial locality* sangat tinggi dalam CPU L1 cache.
10. Provenance menyatakan bahwa pointer membawa asosiasi tak kasat mata tentang alokasi sumbernya. Membandingkan alamat dua objek terpisah secara rasional (`<`, `>`) tidak memiliki arti semantik matematis dalam ruang alamat linier abstrak standar C, sehingga diklasifikasikan sebagai *Undefined Behavior* untuk membebaskan kompiler memindahkan lokasi objek di stack/heap saat optimasi.

#### Solusi Bagian C: Skenario Kasus Produksi
11. **Akar Masalah**: Arsitektur ARM64 sangat ketat terhadap *Hardware Memory Alignment*. Ada potongan kode yang melakukan casting pointer bita mentah `uint8_t*` langsung ke tipe multi-bita (`uint32_t*` atau `uint64_t*`) pada alamat yang bukan kelipatan 4 atau 8. Arsitektur x86_64 memiliki silikon ekstra untuk menangani unaligned access secara otomatis (sehingga lolos saat dev), namun ARM64 membangkitkan alignment fault trap ke kernel yang memicu `SIGBUS`.
    *Solusi:* Gunakan `memcpy` untuk membaca nilai, atau bungkus struct dengan atribut `__attribute__((packed, aligned(1)))`.
12. **Akar Masalah**: Pelanggaran *Strict Aliasing Rule*. Pada `-O0`, kompiler menulis dan membaca register ke RAM secara sekuensial naif. Pada `-O3`, *Type-Based Alias Analysis (TBAA)* aktif: Kompiler mengasumsikan pointer `network_rx_buffer` (misal array integer/karakter) tidak akan pernah menimpa tipe struct `Header`. Kompiler mengacak urutan instruksi *store* dan *load* (*Instruction Reordering*), menyebabkan pembacaan field header mengeksekusi data lama yang belum ditulis.
    *Solusi:* Kompilasi dengan `-fno-strict-aliasing` atau perbaiki pembacaan payload stream menggunakan aliansi byte-level legal atau `memcpy`.
13. **Akar Masalah**: **False Sharing**. Pointer `ptr_a` dan `ptr_b` menunjuk ke alamat data yang secara kebetulan berada di dalam **Cache Line 64-byte yang sama**. Ketika Core 1 menulis ke `ptr_a`, *Cache Coherency Protocol* perangkat keras (MESI Protocol) secara agresif membatalkan (invalidate) seluruh cache line di Core 2, memaksa Core 2 membaca ulang dari memori lambat, dan sebaliknya (cache ping-ponging).
    *Solusi:* Pisahkan data `ptr_a` dan `ptr_b` ke cache line terpisah menggunakan padding atau spesifikasi alignment: `_Alignas(64)`.

---

## 16. Summary
- Pointer dalam C modern adalah abstraksi virtual yang dikelola oleh translasi perangkat keras (MMU/TLB) dan terikat erat pada karakteristik CPU Cache.
- **Pointer Arithmetic** beroperasi secara proporsional terhadap ukuran data tipe (`sizeof(*ptr)`). Untuk inspeksi mentah tingkat bita, selalu gunakan `uint8_t*` atau `char*`.
- **Strict Aliasing Rule** dan **Pointer Provenance** adalah pilar optimasi kompiler modern: mengabaikannya akan mengakibatkan *undefined behavior* sistemik yang sangat sulit dilacak pada optimasi level tinggi (`-O2`/`-O3`).
- Pada arsitektur produksi kelas enterprise, ketergantungan pada `malloc()` dan `free()` standar harus digantikan atau diabstraksikan menggunakan **Custom Allocator (Arena, Fixed Pool, Ring Buffer)** guna menjamin alokasi $O(1)$, zero fragmentation, spatial cache locality maksimal, dan latensi deterministik sub-mikrodetik.