# SEKSI 01 — IDENTITAS MODUL

* **Kurikulum:** Bahasa Pemrograman C Tingkat Mahir (*Advanced Systems Programming*)
* **Kategori:** 02-Programming-Languages
* **Bab:** 07 — Manajemen Memori Tingkat Lanjut & Pola Alokasi
* **Modul:** 01 — Manajemen Memori Dinamis: Subalokator & Profiling
* **Tingkat Kesulitan:** Advanced / Lanjutan
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang penunjuk (*pointers*), aritmatika penunjuk (*pointer arithmetic*), dan dereferensi memori.
  * Pemahaman siklus hidup memori standar: segmen *Stack*, *Heap*, *BSS*, *Data*, dan *Text*.
  * Pemahaman antarmuka alokator bawaan POSIX/C Runtime (`malloc`, `calloc`, `realloc`, `free`, `posix_memalign`).
  * Konsep dasar tata letak memori virtual (*virtual memory pages*, MMU, *page faults*).
* **Target Lingkungan Kompilasi:**
  * Standar: ISO/IEC 9899:2011 (C11) atau ISO/IEC 9899:2018 (C17).
  * Kompiler: GCC 11+ / Clang 13+ pada Linux x86_64 atau ARM64.
  * Opsi Kompiler Wajib: `-std=c11 -Wall -Wextra -Wpedantic -Wconversion -Wshadow -O2`

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Keterbatasan Alokator Umum (*General-Purpose Allocators*):** Menjelaskan secara matematis dan arsitektural mengapa fungsi `malloc()` dan `free()` standar (seperti `ptmalloc3`, `jemalloc`, atau `tcmalloc`) tidak optimal untuk sistem *real-time*, mesin permainan (*game engines*), dan komputasi frekuensi tinggi (*high-frequency trading*) akibat *metadata overhead*, fragmentasi eksternal, dan latensi nondeterministik ($\mathcal{O}(N)$ *worst-case*).
2. **Merancang dan Mengimplementasikan Arena/Linear Allocator:** Membangun alokator berbasis *arena bump-pointer* yang mampu melakukan alokasi deterministik $\mathcal{O}(1)$ dan pelepasan memori massal (*bulk deallocation*) dalam $\mathcal{O}(1)$ dengan penanganan batas penyelarasan (*data alignment*) perangkat keras.
3. **Merancang dan Mengimplementasikan Pool/Fixed-Size Allocator:** Mengembangkan *freelist-based pool allocator* yang mengeliminasi fragmentasi eksternal untuk struktur data dengan ukuran homogen, dengan operasi alokasi dan dealokasi strictly $\mathcal{O}(1)$.
4. **Menguasai Aritmatika Penyelarasan Memori (*Memory Alignment Arithmetic*):** Mengimplementasikan algoritma *bitwise alignment masking* guna memastikan seluruh blok memori mematuhi batasan arsitektur mikro prosesor (`alignof(max_align_t)` dan batasan cache line 64-byte).
5. **Melakukan Profiling dan Diagnostik Memori Mendalam:** Menggunakan peralatan diagnostik industri modern (*AddressSanitizer*, *LeakSanitizer*, dan *Valgrind Massif*) serta mengimplementasikan *memory tracking harness* kustom untuk mengukur konsumsi *peak memory/high-water mark*, rasio fragmentasi, dan mendeteksi akses memori liar (*out-of-bounds/use-after-free*).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Memori sebagai Sumber Daya Deterministik
Pada pemrograman pemula, *heap* diperlakukan sebagai ruang tak berhingga tempat objek dapat dialokasikan dan didealokasikan secara acak kapan pun dibutuhkan melalui panggilan fungsi `malloc` dan `free`. Dalam rekayasa sistem berkinerja tinggi (*high-performance systems engineering*), mental model ini adalah sebuah kecacatan arsitektural.

Sistem alokator bawaan sistem operasi (OS) harus melayani beban kerja heterogen sembarang (*arbitrary heterogeneous workloads*). Untuk mencapai generalitas tersebut, alokator bawaan harus:
1. Menyimpan metadata alokasi (*chunk headers*, bitflags, ukuran blok) tepat di samping data Anda (*in-band metadata*).
2. Menggunakan algoritma pencarian ruang kosong (*best-fit*, *first-fit*, atau *segregated lists*) yang membutuhkan traversal memori.
3. Melakukan sinkronisasi multithreading (*mutex locking*) saat terjadi kontensi *heap*.
4. Mengeluarkan instruksi transisi *user-space* ke *kernel-space* (`brk` atau `mmap`) saat memori virtual internal habis.

Hal-hal tersebut memperkenalkan **latensi non-deterministik**, **fragmentasi memori**, dan **cache invalidation**.

```
Mental Model Tradisional (Naif):
[Aplikasi] ---> malloc(N) ---> [ptmalloc: Search bin -> Lock Mutex -> (brk/mmap) -> Split Chunk] ---> Penunjuk Memori
           ---> free(p)   ---> [ptmalloc: Lock Mutex -> Coalesce Chunks -> Update Bins]

Mental Model Systems Engineer:
[Sistem Operasi] --- (Alokasi 1x Blok Memori Raksasa: Monolithic Slab) ---> [Aplikasi Subalokator]
                                                                                   |
         +-------------------------------------------------------------------------+
         |
         v
[Subalokator Kustom]:
  |-- Arena Allocator  : Siklus hidup sementara (per-frame/per-request). Majukan pointer; reset = 0.
  |-- Pool Allocator   : Entitas diskrit berukuran tetap. Freelist tersemat di memori yang tidak dipakai.
  `-- Scratchpad/Stack : Sub-alokasi LIFO cepat menggunakan marker.
```

### Filosofi Kepemilikan dan Siklus Hidup (*Lifetimes & Ownership*)
Sebelum mengalokasikan satu bita pun, jawablah tiga pertanyaan ini:
1. **Berapa ukuran blok ini?** (Apakah selalu konstan, atau bervariasi?)
2. **Kapan blok ini akan mati?** (Apakah mati bersamaan dengan objek lain dalam satu fase/siklus kerja, atau mati secara acak?)
3. **Siapa yang memiliki blok ini?** (Apakah kepemilikan tunggal terlokalisasi, atau dibagikan antar-thread?)

Jika sekumpulan alokasi memiliki *lifetime* yang identik (misalnya, semua entitas yang dibuat untuk memproses satu frame HTTP request atau satu frame rendering grafis), mereka **harus** dikelompokkan ke dalam satu alokator arena. Alokasi individual tidak boleh dibebaskan satu per satu; seluruh arena dibebaskan sekaligus (*instant wholesale wipe*).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram arsitektur dua subalokator mendasar: **Arena (Linear) Allocator** dan **Pool (Fixed-Block) Allocator**.

### 1. Arena (Linear/Bump) Allocator Architecture
Alokasi dilakukan dengan memajukan kursor penunjuk penyeimbang (*offset*). Operasi `free` individual tidak didukung; hanya reset global yang diperbolehkan.

```
+-------------------------------------------------------------------------------+
|                            MEMORY SLAB (Kapasitas C)                          |
+==================+==================+==================+----------------------+
| Blok Alokasi 1   | Blok Alokasi 2   | Blok Alokasi 3   | Memori Bebas (Sisa)  |
| Data Payload     | Data Payload     | Data Payload     |                      |
+==================+==================+==================+----------------------+
^                  ^                  ^                  ^                      ^
|                  |                  |                  |                      |
Offset 0           Offset A           Offset B           Kursor Saat Ini        Batas Kapasitas
                                                         (Alloc Offset)         (Capacity)

Operasi Alokasi:
  current_ptr = base + alloc_offset
  aligned_ptr = ALIGN_FORWARD(current_ptr, alignment)
  new_offset  = (aligned_ptr - base) + size
  if new_offset <= capacity:
      alloc_offset = new_offset
      return aligned_ptr
  else:
      return OUT_OF_MEMORY (OOM)

Operasi Free:
  alloc_offset = 0 (Semua memori seketika tersedia kembali)
```

### 2. Pool (Fixed-Size Block) Allocator Architecture
Memori dibagi menjadi $N$ slot berukuran sama. Blok-blok yang belum terpakai dirangkai menggunakan struktur data *Singly-Linked Intrusive Free-List*. Penunjuk *next* disimpan langsung di dalam blok kosong tersebut tanpa memakan memori tambahan (*zero overhead*).

```
State Awal (Sebelum Ada Alokasi):
  Free-List Head Pointer
         |
         v
      +--------------+      +--------------+      +--------------+
      |  Slot 0      | ---> |  Slot 1      | ---> |  Slot 2      | ---> NULL
      | (Next Node)  |      | (Next Node)  |      | (Next Node)  |
      +--------------+      +--------------+      +--------------+

Setelah Alokasi 1 Unit (Slot 0 Diambil oleh Aplikasi):
  Free-List Head Pointer
         |
         v
      +--------------+      +--------------+
      |  Slot 1      | ---> |  Slot 2      | ---> NULL
      +--------------+      +--------------+
      
      [ Slot 0 Dialokasikan: Berisi Data Payload Milik Aplikasi ]

Setelah Dealokasi Slot 0:
  Slot 0 dimasukkan kembali ke kepala (head) dari Free-List:
  Free-List Head Pointer
         |
         v
      +--------------+      +--------------+      +--------------+
      |  Slot 0      | ---> |  Slot 1      | ---> |  Slot 2      | ---> NULL
      +--------------+      +--------------+      +--------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Aritmatika Penyelarasan Memori (*Data Alignment*)
Pada prosesor modern (x86_64, ARM64), data tipe primitif wajib atau sangat disarankan untuk diakses pada alamat memori yang merupakan kelipatan dari ukurannya sendiri (misalnya `uint32_t` pada alamat kelipatan 4, `uint64_t` atau penunjuk pada alamat kelipatan 8). 

Jika penyelarasan dilanggar:
* Pada arsitektur x86_64: Menghasilkan penalti kinerja karena prosesor harus melakukan dua siklus pembacaan memori (*split-lock / unaligned memory access*).
* Pada beberapa arsitektur ARM, MIPS, dan SPARC: Menyebabkan interupsi kesalahan perangkat keras (*Hardware Alignment Fault Exception* / `SIGBUS`).

Formula matematis untuk memajukan alamat memori $P$ menuju kelipatan penyelarasan berikutnya $A$ (di mana $A$ adalah bilangan pangkat dua: $2^n$):

$$\text{Penyelarasan Maju: } P_{\text{aligned}} = (P + (A - 1)) \ \& \ \sim(A - 1)$$

*Penjelasan Operasi Bitwise:*
* $A - 1$: Menghasilkan masker (*mask*) bit-bit rendah bernilai 1. Contoh untuk $A = 8$ (`00001000`): $A - 1 = 7$ (`00000111`).
* $P + (A - 1)$: Menambahkan nilai offset maksimum yang mungkin dibutuhkan untuk mencapai kelipatan terdekat tanpa melompati batas kelipatan berikutnya.
* $\sim(A - 1)$: Membalik bit masker. Untuk $A = 8$: $\sim(7) = \text{semua bit 1 kecuali 3 bit terbawah}$ (`...11111000`).
* Operasi `&` (*bitwise AND*): Meng-nol-kan bit-bit residu yang tidak selaras, menjamin hasil akhir merupakan kelipatan persis dari $A$.

### 2. Intrusive Free-List dalam Pool Allocator
Konsep paling fundamental dari efisiensi ruang pada *Pool Allocator* adalah ketiadaan metadata eksternal per-blok. Saat sebuah blok tidak digunakan (*free*), ia tidak menyimpan data pengguna. Oleh karena itu, kita dapat menggunakan ruang memori blok tersebut untuk menyimpan penunjuk (*pointer*) ke blok kosong berikutnya:

```c
typedef struct PoolNode {
    struct PoolNode* next;
} PoolNode;
```

Ukuran minimum setiap slot dalam Pool Allocator adalah:
$$\text{Slot Size} = \max(\text{Ukuran Objek Aktual}, \ \text{sizeof(PoolNode*)})$$

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Masalah Matematika Fragmentasi
Fragmentasi memori terjadi dalam dua bentuk:
* **Fragmentasi Internal:** Terjadi ketika alokator memberikan memori yang lebih besar dari yang diminta aplikasi (misalnya meminta 19 bita, dialokasikan blok 32 bita karena batasan alignment atau bucket sizes). Ruang sisa sebesar 13 bita terbuang percuma.
* **Fragmentasi Eksternal:** Terjadi ketika total memori bebas secara kumulatif mencukupi untuk melayani alokasi baru, namun memori bebas tersebut terpecah-pecah menjadi celah-celah kecil yang saling terpisah, sehingga tidak ada satu pun ruang kontigu yang cukup besar untuk alokasi tersebut.

Secara formal, rasio fragmentasi eksternal ($E$) dapat dinyatakan sebagai:
$$E = 1 - \left( \frac{\text{Ukuran Blok Bebas Kontigu Terbesar}}{\text{Total Memori Bebas}} \right)$$

Jika aplikasi berjalan terus menerus (*long-running daemon*), $E \to 1$, yang berarti `malloc()` akan mulai gagal mengembalikan memori (`NULL`) meskipun metrik *Total Free Memory* masih menunjukkan angka gigabytes. Subalokator arena memecahkan masalah fragmentasi eksternal sepenuhnya dengan mereduksi $E = 0$ dalam masa hidup arena tersebut.

### 2. Hierarki Cache dan Cache-Line Bouncing
Cache CPU modern tersusun dalam baris memori (*cache lines*) yang biasanya berukuran 64 bita. 

Panggilan `malloc()` standar yang berulang-ulang akan menghasilkan penunjuk yang tersebar secara acak (*spatially dispersed*) di seluruh ruang alamat virtual. Ketika kode Anda melakukan iterasi melalui array penunjuk ini:
* Setiap dereferensi penunjuk memicu **L1/L2 Cache Miss**.
* Kontroler memori harus membaca 64 bita penuh dari RAM utama (membutuhkan 200-300 siklus CPU).

Sebaliknya, **Arena Allocator** menata alokasi secara berturut-turut pada alamat fisik/virtual yang bersebelahan (*spatial locality*). Ketika CPU mengambil Objek A ke dalam L1 cache, Objek B yang berada tepat di samping Objek A secara otomatis terambil ke dalam cache yang sama tanpa latensi tambahan (*hardware spatial prefetching*).

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi lengkap, murni, dan aman dari **Arena Allocator** serta **Pool Allocator** yang memenuhi standar C11, mencakup penanganan *alignment* manual yang ketat.

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>
#include <stdalign.h>

/* ========================================================================== */
/*                UTILITY: ALIGNMENT HELPER                                   */
/* ========================================================================== */

static inline uintptr_t align_forward_uintptr(uintptr_t ptr, uintptr_t alignment) {
    assert((alignment & (alignment - 1)) == 0 && "Alignment must be a power of 2!");
    return (ptr + (alignment - 1)) & ~(alignment - 1);
}

/* ========================================================================== */
/*                IMPLEMENTASI 1: ARENA (LINEAR) ALLOCATOR                    */
/* ========================================================================== */

typedef struct {
    uint8_t *buffer;
    size_t   capacity;
    size_t   offset;
    size_t   prev_offset;
} Arena;

Arena arena_create(size_t capacity) {
    Arena a;
    a.capacity = capacity;
    a.offset = 0;
    a.prev_offset = 0;
    a.buffer = (uint8_t *)malloc(capacity);
    if (!a.buffer) {
        perror("Gagal mengalokasikan arena buffer");
        exit(EXIT_FAILURE);
    }
    return a;
}

void* arena_alloc_align(Arena *arena, size_t size, size_t alignment) {
    uintptr_t current_ptr = (uintptr_t)(arena->buffer + arena->offset);
    uintptr_t aligned_ptr = align_forward_uintptr(current_ptr, alignment);
    
    size_t new_offset = (size_t)(aligned_ptr - (uintptr_t)arena->buffer) + size;

    if (new_offset > arena->capacity) {
        /* Out of Memory di dalam Arena */
        return NULL;
    }

    arena->prev_offset = arena->offset;
    arena->offset = new_offset;
    return (void *)aligned_ptr;
}

void* arena_alloc(Arena *arena, size_t size) {
    /* Penyelarasan default adalah ukuran pointer mesin */
    return arena_alloc_align(arena, size, alignof(max_align_t));
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
    arena->prev_offset = 0;
}

/* ========================================================================== */
/*                IMPLEMENTASI 2: POOL (FIXED-SIZE) ALLOCATOR                 */
/* ========================================================================== */

typedef struct PoolNode {
    struct PoolNode *next;
} PoolNode;

typedef struct {
    uint8_t  *buffer;
    size_t    object_size;
    size_t    capacity;
    PoolNode *free_list;
} Pool;

Pool pool_create(size_t object_size, size_t num_objects) {
    Pool p;
    /* Ukuran slot harus memuat minimal struktur PoolNode */
    size_t actual_size = object_size < sizeof(PoolNode) ? sizeof(PoolNode) : object_size;
    /* Pastikan slot selaras dengan max_align_t */
    actual_size = (size_t)align_forward_uintptr((uintptr_t)actual_size, alignof(max_align_t));
    
    p.object_size = actual_size;
    p.capacity    = num_objects;
    p.buffer      = (uint8_t *)malloc(actual_size * num_objects);
    
    if (!p.buffer) {
        perror("Gagal mengalokasikan pool buffer");
        exit(EXIT_FAILURE);
    }

    /* Bangun singly-linked intrusive free list */
    p.free_list = (PoolNode *)p.buffer;
    PoolNode *curr = p.free_list;
    for (size_t i = 0; i < num_objects - 1; ++i) {
        uint8_t *next_addr = (uint8_t *)curr + p.object_size;
        curr->next = (PoolNode *)next_addr;
        curr = curr->next;
    }
    curr->next = NULL;

    return p;
}

void* pool_alloc(Pool *pool) {
    if (pool->free_list == NULL) {
        /* Pool exhausted */
        return NULL;
    }

    PoolNode *node = pool->free_list;
    pool->free_list = node->next;
    return (void *)node;
}

void pool_free(Pool *pool, void *ptr) {
    if (ptr == NULL) return;

    /* Verifikasi apakah penunjuk berada di dalam rentang buffer memori pool */
    uintptr_t p_addr = (uintptr_t)ptr;
    uintptr_t start  = (uintptr_t)pool->buffer;
    uintptr_t end    = start + (pool->object_size * pool->capacity);

    assert(p_addr >= start && p_addr < end && "Pointer di luar jangkauan pool!");
    assert((p_addr - start) % pool->object_size == 0 && "Pointer tidak selaras dengan grid pool!");

    PoolNode *node = (PoolNode *)ptr;
    node->next = pool->free_list;
    pool->free_list = node;
}

void pool_destroy(Pool *pool) {
    if (pool->buffer) {
        free(pool->buffer);
        pool->buffer = NULL;
    }
    pool->free_list = NULL;
    pool->capacity = 0;
    pool->object_size = 0;
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Logika Internal Arena Allocator
1. **Fungsi `align_forward_uintptr`:**
   * Baris `assert((alignment & (alignment - 1)) == 0);`: Memastikan bilangan penyelarasan adalah $2^n$. Jika bukan, bitwise trick tidak akan bekerja.
   * Baris `return (ptr + (alignment - 1)) & ~(alignment - 1);`: Menghitung alamat terdekat ke atas yang bit-bit penyelarasan terbawahnya nol.
2. **Fungsi `arena_alloc_align`:**
   * Baris `uintptr_t current_ptr = (uintptr_t)(arena->buffer + arena->offset);`: Menghitung alamat mentah saat ini berdasarkan offset lama.
   * Baris `uintptr_t aligned_ptr = align_forward_uintptr(current_ptr, alignment);`: Menggeser penunjuk ke batas aman alignment CPU.
   * Baris `size_t new_offset = (size_t)(aligned_ptr - (uintptr_t)arena->buffer) + size;`: Menghitung offset total baru dari pangkal buffer.
   * Baris `if (new_offset > arena->capacity) return NULL;`: Validasi *Bounds Checking*. Menjamin tidak ada *buffer overflow* pada heap induk.
   * Baris `arena->offset = new_offset;`: Memajukan offset (pola alokasi *bump pointer*). Operasi ini strictly $\mathcal{O}(1)$ deterministik tanpa pencarian tabel memori.

### Analisis Logika Internal Pool Allocator
1. **Inisialisasi `pool_create`:**
   * Baris `actual_size = (size_t)align_forward_uintptr((uintptr_t)actual_size, alignof(max_align_t));`: Memastikan bahwa setiap sel/slot objek memiliki ukuran yang memenuhi kelipatan `max_align_t`. Jika ukuran objek adalah 12 bita pada sistem 64-bit, ia dibulatkan ke 16 bita.
   * Loop `for (size_t i = 0; i < num_objects - 1; ++i)`: Merangkai setiap blok kosong ke blok sesudahnya menggunakan penunjuk `next`. Blok memori digunakan sebagai node itu sendiri.
2. **Fungsi `pool_alloc`:**
   * Baris `PoolNode *node = pool->free_list;`: Mengambil elemen terdepan dari daftar kosong.
   * Baris `pool->free_list = node->next;`: Memperbarui pointer *head*. Kompleksitas waktu: tepat 2 instruksi mesin, $\mathcal{O}(1)$.
3. **Fungsi `pool_free`:**
   * Validasi ganda `assert(...)`: Memastikan penunjuk benar-benar merupakan anggota memori pool dan berada tepat pada batas stride blok (`(p_addr - start) % pool->object_size == 0`). Ini mencegah korupsi freelist akibat *wild pointer*.
   * Baris `node->next = pool->free_list; pool->free_list = node;`: Menyisipkan kembali blok bekas ke awal *head* freelist. Tidak ada pergeseran memori (*no memory shifts*).

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Engine Pemrosesan Paket Jaringan Berkecepatan Tinggi (Network Packet Broker)
Pada arsitektur jaringan *High-Frequency Trading* (HFT) atau *packet sniffer* 10 Gbps (menggunakan DPDK/AF_XDP), aplikasi menerima hingga 14.88 juta paket per detik (*packets per second*). 

Setiap frame jaringan Ethernet berukuran bervariasi antara 64 hingga 1518 bita (MTU standar). Apabila program menggunakan alokasi umum `malloc()` dan `free()` untuk setiap paket yang masuk:
1. Terjadi **kontensi penguncian (*lock contention*)** pada *allocator arena* sistem ketika banyak thread IO menerima paket serentak.
2. Terjadi lonjakan latensi p99 dan p99.9 (*tail latency spikes*) akibat operasi *coalescing* dari `ptmalloc`.
3. Memori tervirtualisasi mengalami fragmentasi berat setelah berjalan selama 4 jam, menyebabkan *Out of Memory* (OOM) meskipun memori fisik sistem masih tersisa 40%.

### Solusi Rekayasa
Menggunakan arsitektur memori bertingkat:
1. **Fixed-Size Pool Allocator** dialokasikan di awal untuk menampung *Packet Descriptors* (struktur data kontrol berukuran tetap).
2. **Ring of Arena Allocators** per-thread pemrosesan (masing-masing berukuran 4 MB). Setiap *batch* pembacaan paket (misal 32 paket) mengalokasikan payload langsung pada Arena lokal. Setelah *batch* selesai dikirimkan ke pipa analisis, Arena di-reset dalam $\mathcal{O}(1)$ seketika.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem pemrosesan paket jaringan mini dengan instrumentasi metrik memori bawaan (*profiling telemetry*).

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <time.h>
#include <stdalign.h>

#define MAX_PACKET_PAYLOAD 1536
#define BATCH_SIZE 8
#define TOTAL_BATCHES 5

/* Struktur Metrik Observabilitas */
typedef struct {
    size_t total_allocations;
    size_t total_deallocations;
    size_t current_bytes_used;
    size_t peak_bytes_used;
} MemoryMetrics;

static MemoryMetrics g_metrics = {0};

/* Forward Declaration Helper */
static inline uintptr_t align_forward(uintptr_t ptr, uintptr_t alignment) {
    return (ptr + (alignment - 1)) & ~(alignment - 1);
}

/* --- ARENA SUBALLOCATOR DENGAN PROFILING --- */
typedef struct {
    uint8_t *buffer;
    size_t capacity;
    size_t offset;
} MonitoredArena;

MonitoredArena monitored_arena_create(size_t capacity) {
    MonitoredArena a;
    a.capacity = capacity;
    a.offset = 0;
    a.buffer = (uint8_t *)aligned_alloc(64, capacity); /* Selaras Cache-line 64-byte */
    if (!a.buffer) {
        perror("Alokasi memori buffer arena gagal");
        exit(EXIT_FAILURE);
    }
    return a;
}

void* monitored_arena_alloc(MonitoredArena *arena, size_t size) {
    uintptr_t cur = (uintptr_t)(arena->buffer + arena->offset);
    uintptr_t aligned = align_forward(cur, alignof(max_align_t));
    size_t padding = (size_t)(aligned - cur);
    size_t new_offset = arena->offset + padding + size;

    if (new_offset > arena->capacity) {
        return NULL;
    }

    arena->offset = new_offset;

    /* Update Telemetri */
    g_metrics.total_allocations++;
    g_metrics.current_bytes_used = arena->offset;
    if (g_metrics.current_bytes_used > g_metrics.peak_bytes_used) {
        g_metrics.peak_bytes_used = g_metrics.current_bytes_used;
    }

    return (void *)aligned;
}

void monitored_arena_reset(MonitoredArena *arena) {
    g_metrics.total_deallocations += g_metrics.total_allocations;
    arena->offset = 0;
    g_metrics.current_bytes_used = 0;
}

void monitored_arena_destroy(MonitoredArena *arena) {
    if (arena->buffer) {
        free(arena->buffer);
        arena->buffer = NULL;
    }
}

/* --- REKAYASA SISTEM PAKET JARINGAN --- */
typedef struct {
    uint32_t packet_id;
    uint32_t timestamp;
    size_t   payload_size;
    uint8_t *payload;
} NetworkPacket;

void process_network_packet(NetworkPacket *pkt) {
    /* Simulasi pemrosesan paket (misal: verifikasi checksum payload) */
    uint32_t checksum = 0;
    for (size_t i = 0; i < pkt->payload_size; ++i) {
        checksum ^= pkt->payload[i];
    }
    (void)checksum; // Mengabaikan peringatan variabel tidak digunakan
}

int main(void) {
    printf("=== SIMULASI PEMROSESAN JARINGAN (SUBALOKATOR AKTIF) ===\n");

    /* Buat Arena per-thread berukuran 64 KB */
    MonitoredArena packet_arena = monitored_arena_create(64 * 1024);

    srand((unsigned int)time(NULL));

    for (int batch = 1; batch <= TOTAL_BATCHES; ++batch) {
        printf("\n--- Memproses Batch #%d ---\n", batch);
        
        NetworkPacket packets[BATCH_SIZE];

        /* Tahap Alokasi Batch */
        for (int i = 0; i < BATCH_SIZE; ++i) {
            packets[i].packet_id = (uint32_t)(batch * 100 + i);
            packets[i].timestamp = (uint32_t)time(NULL);
            /* Ukuran payload heterogen acak antara 64 hingga 1500 bita */
            packets[i].payload_size = 64 + (size_t)(rand() % (MAX_PACKET_PAYLOAD - 64));

            packets[i].payload = (uint8_t *)monitored_arena_alloc(&packet_arena, packets[i].payload_size);

            if (!packets[i].payload) {
                fprintf(stderr, "Fatal: Arena kehabisan memori pada batch %d, paket %d!\n", batch, i);
                exit(EXIT_FAILURE);
            }

            /* Inisialisasi payload tiruan */
            memset(packets[i].payload, (uint8_t)(i & 0xFF), packets[i].payload_size);
        }

        /* Tahap Pemrosesan Paket */
        for (int i = 0; i < BATCH_SIZE; ++i) {
            process_network_packet(&packets[i]);
        }

        printf("Batch #%d Selesai. Penggunaan Memori Saat Ini: %zu bita\n", 
               batch, g_metrics.current_bytes_used);

        /* Reset Memori Seketika: Membebaskan seluruh alokasi batch sekaligus dalam O(1) */
        monitored_arena_reset(&packet_arena);
        printf("Arena di-reset. Penggunaan Memori Setelah Reset: %zu bita\n", g_metrics.current_bytes_used);
    }

    printf("\n=== METRIK PROFILING MEMORI FINAL ===\n");
    printf("Total Alokasi Diterbitkan: %zu kali\n", g_metrics.total_allocations);
    printf("Peak Memory (High-Water Mark): %zu bita\n", g_metrics.peak_bytes_used);
    printf("Fragmentasi Eksternal: 0.00%% (Dieliminasi oleh arsitektur Arena)\n");

    monitored_arena_destroy(&packet_arena);
    return 0;
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih model alokator adalah keputusan rekayasa yang penuh dengan kompromi. Tabel berikut menjabarkan karakteristik teknis masing-masing pendekatan:

| Karakteristik | `malloc` / `free` Sistem | Arena / Linear Allocator | Pool / Free-list Allocator | Buddy Allocator |
| :--- | :--- | :--- | :--- | :--- |
| **Kompleksitas Alokasi** | $\mathcal{O}(1)$ avg / $\mathcal{O}(N)$ worst | Strictly $\mathcal{O}(1)$ | Strictly $\mathcal{O}(1)$ | $\mathcal{O}(\log N)$ |
| **Kompleksitas Dealokasi**| $\mathcal{O}(1)$ avg / $\mathcal{O}(N)$ worst | Tidak mendukung individual | Strictly $\mathcal{O}(1)$ | $\mathcal{O}(\log N)$ |
| **Fragmentasi Eksternal**| Tinggi seiring waktu | **Nol Mutlak** | **Nol Mutlak** | Moderat (karena pembagian biner) |
| **Fragmentasi Internal**| Minimal (terisolasi) | Tergantung padding alignment | Rendah jika objek homogen | Tinggi (membulatkan ke $2^k$) |
| **Overhead Metadata** | 8 - 16 bita per alokasi | **Nol per alokasi** (hanya global) | **Nol per alokasi** (intrusive) | 1-2 bit per node (bitmap) |
| **Safety Terhadap UAF** | Lemah (bergantung OS) | Sangat Tinggi (lifetime terikat) | Moderat (dapat divalidasi) | Moderat |
| **Kasus Penggunaan Ideal**| Alokasi umum masa hidup acak | Alokasi siklis / per-frame | Struktur data seragam (Node/Entity)| Driver kernel, alokasi buffer halaman |

### Kapan Tidak Boleh Menggunakan Arena:
* Objek memiliki masa hidup (*lifetimes*) yang sangat berbeda dan tidak dapat diprediksi.
* Alokasi memori berukuran sangat masif namun berumur panjang, yang akan menahan seluruh sisa arena untuk dibebaskan (*memory pin-down hazard*).

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Power-of-Two Misconception pada Alignment
* **Bahaya:** Melewatkan parameter `alignment` yang bukan pangkat dua (misalnya 3, 5, atau 12) ke formula bitwise `(p + (a - 1)) & ~(a - 1)`.
* **Dampak:** Operasi `~(a - 1)` hanya membentuk topeng pembersih bit rendah yang valid jika $a = 2^n$. Jika diberikan angka 12 (`00001100`), $a - 1 = 11$ (`00001011`), topeng bitwise akan menghasilkan korupsi penunjuk liar yang melompat ke alamat yang salah.

### 2. Pointer Misalignment pada Tipe Data Vektor (AVX-512 / NEON)
* **Bahaya:** Melakukan transmisi (*casting*) pointer yang dihasilkan oleh subalokator ke tipe data intrinsik SIMD (seperti `__m256` atau `__m512`) tanpa meminta alignment 32-byte atau 64-byte.
* **Dampak:** Terjadinya sinyal crash `SIGSEGV` seketika saat instruksi SIMD yang membutuhkan memori selaras dieksekusi (contoh: instruksi mesin `vmovaps`).

### 3. Masalah Minimum Slot Size pada Pool Allocator
* **Bahaya:** Membuat *Pool Allocator* untuk tipe data kecil yang ukurannya lebih kecil daripada pointer sistem, misalnya `char` atau struktur 4-bita pada OS 64-bit:
  ```c
  Pool p = pool_create(sizeof(char), 1024); // BAHAYA!
  ```
* **Dampak:** Ketika freelist dibangun, casting slot menjadi `PoolNode*` akan menulis 8 bita ke dalam slot yang lebarnya hanya 1 bita. Ini menimpa memori slot di sebelahnya (*Adjacent Memory Corruption*).
* **Mitigasi:** Paksa ukuran minimum slot sebesar `sizeof(void*)`:
  ```c
  size_t actual_size = req_size < sizeof(void*) ? sizeof(void*) : req_size;
  ```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. "Use-After-Reset" pada Arena
* **Deskripsi Kesalahan:** Menyimpan pointer objek yang dialokasikan dari Arena melewati batas eksekusi `arena_reset()`.
* **Kode Buruk:**
  ```c
  NetworkPacket *saved_packet = NULL;
  void process_frame(Arena *arena) {
      NetworkPacket *p = (NetworkPacket*)arena_alloc(arena, sizeof(NetworkPacket));
      saved_packet = p; // Mengambil pointer
      arena_reset(arena); // Memori dibebaskan!
  }
  void bad_call(void) {
      saved_packet->packet_id = 42; // FATAL: Use-After-Free (Dangling Pointer)
  }
  ```
* **Pola Perbaikan:** Pointer yang dialokasikan dari Arena tidak boleh bocor keluar dari konteks fungsi yang mengatur arena tersebut. Jika objek harus bertahan lama, ia harus **dikloning** secara eksplisit (*deep copy*) ke alokator berdurasi hidup lebih tinggi (seperti Persistent Heap).

### 2. Destructor Bypass (Leaking Non-Memory Resources)
* **Deskripsi Kesalahan:** Mengalokasikan struktur yang membungkus *file descriptor* (`int fd`), koneksi soket, atau mutex ke dalam arena, lalu mereset arena begitu saja.
* **Akibat:** Memorinya memang bebas, tetapi deskriptor berkas OS bocor selamanya (*resource exhaustion*).
* **Solusi:** Daftarkan fungsi pembersih (*cleanup callback list*) di dalam Arena sebelum reset dipanggil, atau hanya gunakan arena untuk data murni berbentuk *Plain Old Data* (POD).

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Scope Arena Scratchpad (Temp Arena Pattern):**
   Gunakan struktur penanda (*Marker*) untuk mengizinkan pembebasan lokal bergaya LIFO tanpa harus mereset seluruh Arena:
   ```c
   typedef size_t ArenaTemp;

   ArenaTemp arena_temp_begin(Arena *arena) {
       return arena->offset;
   }

   void arena_temp_end(Arena *arena, ArenaTemp temp) {
       assert(temp <= arena->offset && "Marker invalid!");
       arena->offset = temp; // Rollback hanya alokasi lokal
   }
   ```
2. **Definisikan Nilai Penyelarasan Standar Menggunakan Standar C11:**
   Gunakan selalu macro `alignof(max_align_t)` dari `<stdalign.h>` untuk alokasi memori yang tidak secara eksplisit meminta alignment khusus.
3. **Pemberian Nama Konstruktor dan Destruktor yang Jelas:**
   Bedakan siklus hidup dengan akhiran nama yang seragam di seluruh basis kode: `_create()`, `_alloc()`, `_reset()`, dan `_destroy()`.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Pemanfaatan Cache Line Prefetching
Jika Anda memproses memori secara berurutan (*sequential processing*) dari Arena atau Pool, berikan petunjuk (*hint*) kepada modul prefetcher CPU menggunakan GCC/Clang built-in:
```c
__builtin_prefetch(ptr + NEXT_OFFSET, 0, 3);
```
* Parameter 1: Alamat yang ingin dibaca di masa depan.
* Parameter 2: `0` untuk read, `1` untuk write.
* Parameter 3: Skala temporalitas (`3` berarti pertahankan data di semua level cache CPU).

### 2. Mencegah False Sharing pada Lingkungan Multithreading
Ketika alokator digunakan dalam thread terpisah, pastikan struktur alokator masing-masing thread tidak berada dalam baris cache yang sama:
```c
typedef struct {
    alignas(64) Arena arena; // Mencegah thread lain mengotori L1 cache
    alignas(64) uint8_t pad[64 - sizeof(Arena)]; 
} ThreadLocalArena;
```

---

# SEKSI 16 — KEAMANAN & HARDENING

Subalokator kustom tidak memiliki fitur keamanan internal OS secara default (seperti *Address Space Layout Randomization* / ASLR dan *Guard Pages*). Terapkan protokol pertahanan mendalam (*defense-in-depth*) berikut:

### 1. Canary Protection (Canary Cookies)
Selipkan bilangan integritas (*magic number*) sebelum dan sesudah data payload yang dikembalikan ke pengguna untuk mendeteksi *buffer overflow* lokal:
```c
#define CANARY_MAGIC 0xDEADC0DEDEADC0DEULL

typedef struct {
    uint64_t canary_head;
} AllocHeader;

typedef struct {
    uint64_t canary_tail;
} AllocFooter;
```

### 2. Poisoning Memory on Allocation & Free
Gunakan nilai-nilai heksadesimal penanda kerusakan yang dikenal untuk mengidentifikasi memori mati:
* Saat alokator di-reset, timpa memori dengan pola byte `0xCD` (*Clean/Deallocated*).
* Saat alokasi baru diberikan tanpa inisialisasi, isi dengan `0xCC` atau `0xAA`.
Jika debugger melihat aplikasi mencoba membaca alamat `0xCDCDCDCD`, Anda langsung tahu kode tersebut mengidap *Use-After-Free*.

### 3. Pembersihan Data Sensitif (Zeroization)
Untuk Arena yang menangani data kriptografi atau kredensial, jangan gunakan fungsi `memset()` standar karena sering kali dihilangkan oleh optimasi agresif kompiler (*Dead Store Elimination*). Gunakan `explicit_bzero` (POSIX) atau implementasi `volatile`:
```c
void secure_arena_wipe(Arena *arena) {
    volatile uint8_t *p = arena->buffer;
    size_t n = arena->offset;
    while (n--) {
        *p++ = 0;
    }
    arena->offset = 0;
}
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Kompilasi dengan Sanitizer Modern
Alokator kustom memotong alur `malloc()`, sehingga perangkat lunak *AddressSanitizer* (ASan) secara bawaan tidak dapat mengetahui batas antar blok dalam subalokator Anda. Anda harus mengkompilasi modul dengan opsi:
```bash
gcc -std=c11 -Wall -fsanitize=address,undefined -g file.c -o program
```
Untuk mengintegrasikan pemantauan eksplisit, sertakan pustaka `<sanitizer/asan_interface.h>` dan gunakan:
* `ASAN_POISON_MEMORY_REGION(addr, size)`: Menandai memori sebagai terlarang untuk disentuh.
* `ASAN_UNPOISON_MEMORY_REGION(addr, size)`: Menandai memori sebagai valid untuk diakses aplikasi.

### 2. Memetakan High-Water Mark Menggunakan Profiler Eksternal
Untuk menganalisis jejak footprint heap aplikasi Anda secara grafis tanpa mengubah basis kode, jalankan perangkat analisis Valgrind Massif:
```bash
valgrind --tool=massif --massif-out-file=massif.out ./program
ms_print massif.out
```
Massif akan menggambar grafik visual pohon alokasi yang menunjukkan titik tertinggi (*peak allocation time*) di terminal.

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Rumus Kunci & Snippet Siap Pakai

* **Bitwise Forward Alignment:**
  ```c
  #define ALIGN_UP(addr, align) (((uintptr_t)(addr) + ((align) - 1)) & ~((uintptr_t)(align) - 1))
  ```

* **Bump Pointer Allocation Logic:**
  ```c
  void* ptr = (void*)ALIGN_UP(arena->base + arena->offset, align);
  size_t next_offset = ((uintptr_t)ptr - (uintptr_t)arena->base) + size;
  if (next_offset <= arena->capacity) {
      arena->offset = next_offset;
      return ptr;
  }
  return NULL; // OOM
  ```

* **Free-List Intrusive Insertion (Pool Dealloc):**
  ```c
  ((PoolNode*)freed_ptr)->next = pool->head;
  pool->head = (PoolNode*)freed_ptr;
  ```

* **Free-List Intrusive Extraction (Pool Alloc):**
  ```c
  PoolNode *block = pool->head;
  if (block) pool->head = block->next;
  return (void*)block;
  ```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Ujilah penguasaan konsep Anda terhadap sistem memori tingkat lanjut dengan menjawab pertanyaan di bawah ini:

### Bagian A: Tingkat Dasar (Basic)

1. **Pertanyaan:** Mengapa formula bitwise alignment `(addr + (align - 1)) & ~(align - 1)` hanya bekerja jika nilai `align` adalah bilangan pangkat dua ($2^n$)?
   * *Jawaban:* Karena hanya bilangan pangkat dua yang memiliki representasi biner tepat 1 bit tinggi diikuti oleh deretan bit 0. Mengurangi 1 dari bilangan ini menghasilkan deretan bit 1 di posisi bawah, yang jika dibalik (`~`) membentuk topeng yang mampu membersihkan bit sisa pembagian (*remainder bits*) tepat pada batas kelipatan alokasi.

2. **Pertanyaan:** Apa yang dimaksud dengan Intrusive Linked-List pada *Pool Allocator*?
   * *Jawaban:* Teknik penyimpanan struktur simpul tautan (`next` pointer) langsung di dalam ruang data dari blok memori yang sedang menganggur (*free slot*), sehingga tidak memerlukan alokasi metadata terpisah.

3. **Pertanyaan:** Mengapa pembebasan memori individual (*single element free*) tidak dapat diimplementasikan secara efisien pada *Arena Allocator* dasar?
   * *Jawaban:* Karena Arena beroperasi hanya dengan memajukan satu penunjuk offset (*bump pointer*). Membebaskan elemen di tengah akan menciptakan lubang memori yang tidak dapat ditutup tanpa menggeser data lain atau membangun struktur pelacak celah bebas yang kompleks.

4. **Pertanyaan:** Apa nilai alignment standar yang dijamin oleh `malloc()` pada sistem Linux arsitektur x86_64?
   * *Jawaban:* 16 bita (selaras dengan `alignof(max_align_t)`), yang mampu mengakomodasi tipe skalar terbesar serta pointer.

5. **Pertanyaan:** Operasi matematis apa yang digunakan untuk memeriksa apakah sebuah alamat pointer $P$ selaras dengan alignment $A$?
   * *Jawaban:* `(P & (A - 1)) == 0` (di mana $A$ adalah pangkat dua).

---

### Bagian B: Tingkat Menengah (Intermediate)

6. **Pertanyaan:** Bagaimana Arena Allocator mampu meningkatkan performa *hardware data cache prefetching* secara drastis dibanding alokator bawaan?
   * *Jawaban:* Objek dialokasikan secara kontigu bersebelahan secara fisik dalam memori. Pola akses ini memicu pengenalan aliran alamat sekuensial oleh *hardware stream prefetcher* CPU, memuat data masa depan ke dalam L1 cache sebelum instruksi membacanya.

7. **Pertanyaan:** Perhatikan kode berikut:
   ```c
   struct Entity { int id; };
   Pool p = pool_create(sizeof(struct Entity), 100);
   ```
   Pada arsitektur 64-bit, berapa ukuran riil slot memori yang dialokasikan per entitas di dalam fungsi `pool_create` di atas, dan mengapa?
   * *Jawaban:* 8 bita (atau kelipatan `max_align_t`). Walaupun `sizeof(struct Entity)` bernilai 4 bita, slot memori wajib memiliki ukuran minimal sebesar `sizeof(PoolNode*)` (8 bita pada arsitektur 64-bit) agar tidak terjadi korupsi memori tetangga saat simpul freelist disimpan di dalam slot kosong tersebut.

8. **Pertanyaan:** Apakah pemanggilan `arena_reset()` menyebabkan memori fisik dikembalikan ke kernel OS melalui system call `brk` atau `mmap`?
   * *Jawaban:* Tidak. Pemanggilan `arena_reset()` hanya mengembalikan penunjuk kursor offset internal ke nol. Memori fisik/virtual buffer induk tetap dipertahankan di dalam ruang alamat aplikasi untuk digunakan kembali pada siklus berikutnya tanpa *system call overhead*.

9. **Pertanyaan:** Bagaimana cara mendeteksi kesalahan *double free* pada Pool Allocator jika pengguna memanggil `pool_free()` dua kali pada penunjuk yang sama?
   * *Jawaban:* Dengan melakukan validasi transversal pada freelist (memastikan penunjuk belum ada di dalam rantai freelist) atau memeriksa penanda bit kepemilikan (*allocation bitmap*). Jika terjadi *double free*, linked-list akan membentuk lingkaran tertutup (*circular reference/infinite loop*).

10. **Pertanyaan:** Apa kelemahan utama dari strategi perataan memori *cache-line boundary* (misal meratakan setiap variabel struct ke 64 bita) terhadap penggunaan memori keseluruhan?
    * *Jawaban:* Menyebabkan peningkatan fragmentasi internal yang drastis, membuang ruang buffer untuk bantalan *padding*, serta memperbesar footprint memori yang dapat menurunkan rasio efisiensi penggunaan kapasitas cache L2/L3.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Tantangan Mandiri: Bangun "Stack/Scratchpad Allocator" Lengkap dengan Mekanisme Canary Cookie

Buatlah program C11 mandiri yang mengimplementasikan **Stack Allocator** (alokator LIFO yang lebih fleksibel dari Arena murni). 

#### Spesifikasi Proyek:
1. **Definisi Struktur:**
   Bangun struktur alokator bernama `StackAllocator` yang mengelola sebuah *pre-allocated buffer* berukuran 1 MB.
2. **Implementasi API Wajib:**
   * `StackAllocator stack_create(size_t capacity);`
   * `void* stack_alloc(StackAllocator *stack, size_t size, size_t alignment);`
   * `typedef size_t StackMarker;`
   * `StackMarker stack_get_marker(StackAllocator *stack);`
   * `void stack_free_to_marker(StackAllocator *stack, StackMarker marker);`
   * `void stack_destroy(StackAllocator *stack);`
3. **Mekanisme Hardening Keamanan (Wajib):**
   * Di setiap awal alokasi (sebelum payload dikembalikan), simpan struktur header internal tersembunyi yang menyimpan:
     1. Nilai penanda integritas (*Canary Head*) bernilai `0xDEADBEEFCAFEBABE`.
     2. Jarak pergeseran padding (*offset padding*).
   * Pada fungsi `stack_free_to_marker`, periksa apakah memori di sekitar marker mengalami korupsi atau penyimpangan.
4. **Program Pengujian (Verification Driver):**
   * Buat simulasi stack alokasi dengan kedalaman 3 level pemanggilan fungsi.
   * Lakukan alokasi bertingkat, verifikasi keberhasilan alokasi, simpan marker, alokasikan buffer lokal, lalu lepaskan memori kembali ke marker tersebut (*unwind*).
   * Cetak alamat memori dan pastikan memori yang dilepaskan dapat dialokasikan kembali dengan penyelarasan yang valid dan presisi.

Kompilasi program Anda dengan opsi proteksi maksimum:
```bash
gcc -std=c11 -Wall -Wextra -Wpedantic -Werror -fsanitize=address,undefined -g practical_project.c -o practical_project
```
Pastikan eksekusi berakhir dengan kode keluar `0` tanpa adanya laporan kebocoran memori (*zero memory leak*) dari AddressSanitizer.