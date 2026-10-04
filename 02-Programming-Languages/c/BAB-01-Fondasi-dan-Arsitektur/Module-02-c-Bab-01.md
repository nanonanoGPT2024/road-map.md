# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis dan Membedah Tata Letak Memori Rendah (Low-Level Memory Layout)**: Memahami secara mendalam transisi segmen *Text*, *Data*, *BSS*, *Heap*, dan *Stack* serta relasinya terhadap halaman memori virtual (*Virtual Memory Pages*), MMU (*Memory Management Unit*), dan struktur berkas ELF (*Executable and Linkable Format*).
- **Menguasai Mekanisme Dynamic Linking & ABI Execution Model**: Menganalisis cara kerja *Global Offset Table* (GOT), *Procedure Linkage Table* (PLT), serta konvensi pemanggilan fungsi (*System V AMD64 ABI Calling Convention*) hingga level alokasi register dan penataan frame stack.
- **Mengimplementasikan Pola Desain Manajemen Memori Deterministik**: Mengembangkan alokator memori kustom (*Arena/Bump Allocator* dan *Fixed-Size Block Free List Pool*) berkinerja tinggi, aman dari fragmentasi eksternal, dan *cache-aligned*.
- **Menerapkan Standar Keamanan & Diagnostik Kompilasi Modern**: Mengintegrasikan *AddressSanitizer* (ASan), *UndefinedBehaviorSanitizer* (UBSan), serta aturan *strict aliasing* (`restrict`) ke dalam *pipeline build* produksi.
- **Merancang Arsitektur Perangkat Lunak Skala Enterprise Berbasis C**: Menerapkan pola *opaque pointer* (enkapsulasi data murni), *zero-allocation hot-path*, serta *error propagation* yang aman untuk sistem nir-henti (*mission-critical*).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
1. **Sintaks Dasar Bahasa C (C99/C11)**: Tipe data primitif, kontrol alur (`if`, `switch`, `for`, `while`), dan manipulasi array.
2. **Dasar Pointer dan Referensi Memori**: Operator `*` (dereference) dan `&` (address-of), serta pointer `void*`.
3. **Konsep Dasar Sistem Operasi**: Pengertian proses, memori virtual, *system calls* (khususnya famili POSIX: `brk`, `sbrk`, `mmap`, `munmap`).
4. **Toolchain Linux / POSIX**: Penggunaan dasar GCC/Clang, Make, serta terminal Linux x86_64.

---

## 3. Concept & Internal Architecture

### 3.1 Anatomi Memori Virtual dan Struktur Biner ELF
Ketika sistem operasi mengeksekusi biner C pada arsitektur x86_64, kernel tidak langsung memuat seluruh berkas ke RAM fisik, melainkan memetakannya ke dalam ruang alamat virtual (*Virtual Address Space*) melalui struktur VMA (*Virtual Memory Area*). 

Secara terurut dari alamat rendah (*low address*) ke alamat tinggi (*high address*):

```
+-------------------------------------------------------+ 0x0000000000000000
| Reserved (NULL pointer trap zone, 4KB - 64KB)         | (Page Fault jika diakses)
+-------------------------------------------------------+
| Text Segment (.text, .rodata)                         | Read-Only, Executable (RX)
| - Berisi instruksi mesin & string literal             |
+-------------------------------------------------------+
| Data Segment (.data)                                  | Read-Write (RW)
| - Variabel global & static yang diinisialisasi non-nol|
+-------------------------------------------------------+
| BSS Segment (.bss - Block Started by Symbol)          | Read-Write (RW, Anonymous)
| - Variabel global & static tidak diinisialisasi (nol) | Dialokasikan via On-Demand Zero-Fill
+-------------------------------------------------------+
| Heap (Tumbuh ke atas / menuju high address)           | Read-Write (RW)
| - Dimanipulasi via brk/sbrk atau mmap                 | Dikelola glibc ptmalloc / jemalloc
+-------------------------------------------------------+
| ... Free Address Space / Memory Mapping Segment ...   | Ruang ekspansi shared libraries (.so)
| Shared Libraries (libc.so), mmap() regions            |
+-------------------------------------------------------+
| Stack (Tumbuh ke bawah / menuju low address)          | Read-Write (RW)
| - Stack frames, local vars, return addresses, RBP/RSP | 8MB default limit (RLIMIT_STACK)
+-------------------------------------------------------+
| Kernel Space (0xFFFF800000000000 - 0xFFFFFFFFFFFFFFFF)| Ring 0 Only (Trap jika diakses user)
+-------------------------------------------------------+
```

#### Siklus Hidup Segmen:
1. **`.text` & `.rodata`**: Dipetakan langsung dari segmen `LOAD` ELF dengan proteksi memori `PROT_READ | PROT_EXEC`. Mutasi terhadap `.rodata` (misal penulisan ke `char *s = "hello"; s[0] = 'H';`) memicu interrupt perangkat keras CPU *General Protection Fault* (#GP), yang dikonversi kernel Linux menjadi sinyal `SIGSEGV`.
2. **`.bss`**: Dalam berkas ELF fisik di *disk*, seksi `.bss` hanya memakan beberapa byte untuk mencatat ukuran totalnya (`sh_size`), bukan ukuran datanya. Kernel memanfaatkan optimasi *Zero Page* (Copy-on-Write) untuk menunda alokasi fisik hingga terjadi operasi tulis pertama.
3. **`Stack Frame Execution`**: Setiap pemanggilan fungsi membentuk *Activation Record* (Stack Frame) yang dibatasi oleh register `%rbp` (*Base Pointer*) dan `%rsp` (*Stack Pointer*).

---

### 3.2 Dynamic Linking Deep Dive: GOT, PLT, dan Lazy Binding
Dalam biner modern yang ditautkan secara dinamis (*dynamically linked*), alamat absolut dari pustaka bersama (`libc.so`) belum diketahui saat kompilasi. Mekanisme resolusi dilakukan melalui dua tabel krusial:
1. **Procedure Linkage Table (PLT)**: Berada di segmen `.text` (dapat dieksekusi). Merupakan *trampoline* kode perakitan (*assembly*) yang bertugas melompat ke alamat yang tersimpan di GOT.
2. **Global Offset Table (GOT)**: Berada di segmen `.data` / `.got.plt` (dapat ditulisi). Berisi pointer aktual ke fungsi pustaka yang dituju.

```
Panggilan Kode C:       PLT Stub:                     GOT Entry:                Dynamic Linker (ld.so):
  printf("test");  ---> [printf@plt]              ---> [.got.plt: printf]  ---> [ld-linux.so]
                        JMP *printf@GOT                 *Awalnya menunjuk*       *Mencari symbol printf,*
                        PUSH index                      *kembali ke PLT+1*       *tulis alamat aktual ke*
                        JMP dl_resolve                                           *GOT. Panggilan berikut*
                                                                                 *langsung ke libc printf*
```

*Keamanan Produksi*: Arsitektur enterprise modern menggunakan kompilasi `-Wl,-z,relro,-z,now` (*Full RELRO*). Ini memaksa *dynamic linker* untuk menyelesaikan seluruh simbol saat proses inisialisasi (*startup*), kemudian mengubah proteksi halaman GOT menjadi *read-only* murni via `mprotect()`, secara penuh memitigasi eksploitasi keamanan berbasis *GOT Overwrite*.

---

### 3.3 System V AMD64 ABI: Register Allocation & Stack Alignment
Kinerja performa C tingkat tinggi didorong oleh pemahaman terhadap *Application Binary Interface* (ABI). Pada sistem operasi x86_64 Linux/BSD:
- **Enam Argumen Integer/Pointer Pertama**: Diteruskan langsung melalui register CPU, meminimalisir akses bus memori:
  1. `%rdi` (Argumen 1)
  2. `%rsi` (Argumen 2)
  3. `%rdx` (Argumen 3)
  4. `%rcx` (Argumen 4)
  5. `%r8`  (Argumen 5)
  6. `%r9`  (Argumen 6)
- **Argumen Ke-7 dan Seterusnya**: Di-*push* ke stack secara terbalik.
- **Nilai Kembalian (*Return Value*)**: Disimpan pada `%rax` (atau `%rdx:%rax` untuk tipe 128-bit).
- **Aturan Stack Alignment**: Register `%rsp` **wajib** selaras dengan kelipatan 16 byte (*16-byte aligned*) sebelum eksekusi instruksi `call`. Kegagalan menyelaraskan stack akan memicu crash pada instruksi SIMD/AVX (`movdqa`, `movaps`) di dalam fungsi target.

---

### 3.4 Hardware Cache Coherency & Strict Aliasing
- **L1/L2/L3 Cache Lines**: CPU modern memuat data dari RAM dalam satuan blok 64 byte (*Cache Line*). Struktur data C yang dirancang dengan padding acak akan menyebabkan *Cache Miss* ganda.
- **Strict Aliasing Rule**: Standar C (ISO C11 §6.5/7) menetapkan bahwa kompilator berasumsi dua pointer dengan tipe berbeda tidak akan pernah menunjuk ke lokasi memori yang sama. Kompilator mengabaikan pembacaan ulang jika terjadi modifikasi pada pointer bertipe lain. Kata kunci `restrict` secara eksplisit menjamin kepada kompilator bahwa pointer tersebut adalah satu-satunya akses ke objek yang dirujuk, membuka optimasi vektorisasi SIMD penuh.

---

## 4. Why & What

| Pertanyaan | Penjelasan Arsitektural |
| :--- | :--- |
| **Why not generic `malloc()` everywhere?** | `malloc()` adalah *general-purpose allocator* yang kompleks (menangani locking multithreading, mitigasi fragmentasi, pengelolaan chunk). Dalam sistem latensi rendah (*low-latency trading*, *game engine*, *embedded telematics*), variansi latensi `malloc()` (*jitter*) tidak dapat ditoleransi. Diperlukan alokator deterministik dengan kompleksitas $O(1)$. |
| **What is an Arena Allocator?** | Blok memori kontigu berukuran besar yang dipesan di awal (*pre-allocated*). Alokasi dilakukan dengan menggeser penunjuk offset (*bump pointer*). Dealokasi dilakukan sekaligus dengan mereset offset ke nol, menghilangkan *overhead* pencatatan metadata individual dan mencegah kebocoran memori (*memory leaks*). |
| **Why Strict Aliasing matters?** | Tanpa jaminan aliasing, kompilator harus melakukan instruksi *reload* register dari RAM setiap kali ada penulisan pointer lain, karena takut memori yang dibaca telah tertimpa. Penggunaan `restrict` menginstruksikan CPU untuk mempertahankan nilai dalam register, meningkatkan throughput komputasi hingga 20-40%. |
| **What is Data-Oriented Design (DoD)?** | Transformasi dari *Array of Structures* (AoS) menjadi *Structure of Arrays* (SoA) untuk menjamin pemanfaatan *hardware prefetcher* CPU dan memaksimalkan densitas instruksi SIMD. |

---

## 5. How (Workflow Detail)

### Alur Kerja Transisi Kode Sumber Menjadi Binary Execution Engine

```
[source.c] + [header.h]
       │
       ▼ (1) Preprocessing (cpp) -> Makro ekspansi, include resolution, conditional compilation
[source.i]
       │
       ▼ (2) Compilation Phase (cc1) -> AST, SSA, Register Allocation, Vectorization
[source.s] (Assembly Code)
       │
       ▼ (3) Assembly Phase (as) -> Transformasi instruksi simbolik ke machine opcode
[source.o] (Relocatable Object - ELF)
       │
       ▼ (4) Linker Phase (ld) -> Resolusi simbol eksternal, relocation, RELRO processing
[binary.elf] (Executable)
       │
       ▼ (5) Kernel Execve -> Validasi ELF header, pemetaan VMA, transfer kontrol ke ld.so / _start
[RAM / CPU Registers]
```

### Operasi Eksekusi Memori Deterministik (Arena Pattern)
1. **Fase Inisialisasi**: Panggil `mmap()` atau `malloc()` sekali untuk mengalokasikan blok memori besar (misal: 64MB).
2. **Fase Alokasi (Bump Allocation)**: 
   - Hitung batas padding agar selaras dengan keselarasan alami (*natural alignment*) mesin (8 atau 16 byte via bitwise operation: `(addr + (align - 1)) & ~(align - 1)`).
   - Periksa ketersediaan ruang (*bounds check*).
   - Simpan pointer saat ini sebagai hasil kembalian.
   - Tambahkan offset sebesar ukuran alokasi + padding.
3. **Fase Operasi Run-time**: Jalankan seluruh siklus pemrosesan (misal: penanganan 1 frame game atau 1 HTTP request transaksi).
4. **Fase Reset Massal**: Ubah penunjuk offset kembali ke 0. Tidak ada pemanggilan destruktor individual, tidak ada fragmentasi heap.

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi Manajemen Memori: Kamar Hotel vs Lembaran Kertas Notepad

- **`malloc()` / `free()` Konvensional (Kamar Hotel)**:
  Tamu (variabel) datang dan pergi secara dinamis. Pihak hotel harus mencatat kamar mana yang kosong, membersihkan kasur, dan mencari kamar kosong yang pas ukurannya. Seiring waktu, terjadi *fragmentasi*: ada 10 kamar kosong tapi terpisah-pisah, sehingga rombongan 5 orang tidak bisa memesan kamar yang bersebelahan.
  
- **Arena Allocator (Lembaran Kertas Notepad)**:
  Anda menulis catatan secara urut dari baris pertama ke bawah (*bump pointer*). Anda tidak pernah menghapus kata per kata di tengah lembaran. Begitu satu sesi rapat/transaksi selesai, Anda cukup merobek atau menghapus seluruh halaman sekaligus (*mass reset*). Sangat cepat, teratur, dan tidak menyisakan ruang kosong yang tercecer.

### 6.2 Diagram Struktur Memory Alignment & Padding

Perhatikan bagaimana kompilator menyisipkan *invisible padding* untuk menjaga akses data berada pada kelipatan byte alami:

```
Struktur Tidak Efisien (16 Byte):
struct Unoptimized {
    uint8_t  a;    // 1 byte
    /* 3 byte padding disisipkan di sini oleh kompilator */
    uint32_t b;    // 4 byte (wajib mulai di kelipatan 4)
    uint8_t  c;    // 1 byte
    /* 7 byte padding disisipkan di sini untuk kelipatan total struct */
    uint64_t d;    // 8 byte (wajib mulai di kelipatan 8)
};
[a][pad][pad][pad][b][b][b][b][c][pad][pad][pad][pad][pad][pad][pad][d][d][d][d][d][d][d][d]
|----- 4 byte ----|-- 4 byte -|------------- 8 byte --------------|--------- 8 byte --------|
Total: 24 Byte (8 Byte terbuang sia-sia sebagai padding!)

Struktur Teroptimasi (16 Byte):
struct Optimized {
    uint64_t d;    // 8 byte
    uint32_t b;    // 4 byte
    uint8_t  a;    // 1 byte
    uint8_t  c;    // 1 byte
    /* 2 byte padding akhir */
};
[d][d][d][d][d][d][d][d][b][b][b][b][a][c][pad][pad]
|--------- 8 byte --------|-- 4 byte -|--2b-|-- 2b -|
Total: 16 Byte (Densitas cache meningkat 33.3%!)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Eksplorasi Alamat Memori Segmen Biner

Program ini membuktikan pemisahan segmen memori secara deterministik pada arsitektur target x86_64.

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>

/* Segmen .data: Variabel global terinisialisasi */
int32_t global_initialized_var = 0xDEADBEEF;

/* Segmen .bss: Variabel global tidak terinisialisasi */
int32_t global_uninitialized_var;

/* Segmen .rodata: Konstanta */
const char *const read_only_string = "PRODUCTION_CORE_ENGINE_V1";

void inspect_memory_segments(int32_t depth, int32_t stack_val) {
    /* Segmen Stack: Variabel lokal */
    int32_t local_frame_var = depth;

    printf("[Frame %d] Stack Variable Address : %p\n", depth, (void*)&local_frame_var);
    printf("[Frame %d] Stack Arg Address      : %p\n", depth, (void*)&stack_val);

    if (depth < 2) {
        inspect_memory_segments(depth + 1, stack_val + 10);
    }
}

int main(void) {
    /* Segmen Heap: Alokasi dinamis via glibc ptmalloc */
    void *heap_ptr = malloc(1024);
    if (!heap_ptr) {
        perror("Gagal alokasi heap");
        return EXIT_FAILURE;
    }

    printf("==================== BUKTI SEGMEN MEMORI ====================\n");
    printf("[RODATA] Text/String Literal Address: %p\n", (void*)read_only_string);
    printf("[TEXT]   Function Code Address      : %p\n", (void*)&inspect_memory_segments);
    printf("[DATA]   Initialized Global Address : %p\n", (void*)&global_initialized_var);
    printf("[BSS]    Uninitialized Global Addr  : %p\n", (void*)&global_uninitialized_var);
    printf("[HEAP]   Heap Allocated Address     : %p\n", heap_ptr);
    printf("------------------------------------------------------------\n");

    inspect_memory_segments(0, 100);

    printf("============================================================\n");

    free(heap_ptr);
    return EXIT_SUCCESS;
}
```

---

### 7.2 Practical Example: Enterprise Arena Memory Allocator (Cache-Aligned)

Berikut adalah implementasi alokator arena *production-grade* berkinerja tinggi, thread-agnostik, dengan jaminan *memory alignment* 64-bit/128-bit, serta dilengkapi teknik *sentinel bounds checking*.

```c
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>
#include <sys/mman.h>

#define DEFAULT_ALIGNMENT (sizeof(void*))

typedef struct MemoryArena {
    uint8_t *buffer;
    size_t   capacity;
    size_t   offset;
    size_t   prev_offset;
} MemoryArena;

/**
 * Menginisialisasi Arena menggunakan mmap (Virtual Memory OS langsung)
 * Menjamin memori dialokasikan secara anonim tanpa overhead glibc heap.
 */
bool arena_init(MemoryArena *arena, size_t capacity) {
    if (!arena || capacity == 0) return false;

    /* Alokasi anonim via mmap */
    arena->buffer = (uint8_t *)mmap(
        NULL,
        capacity,
        PROT_READ | PROT_WRITE,
        MAP_PRIVATE | MAP_ANONYMOUS,
        -1,
        0
    );

    if (arena->buffer == MAP_FAILED) {
        arena->buffer = NULL;
        arena->capacity = 0;
        arena->offset = 0;
        arena->prev_offset = 0;
        return false;
    }

    arena->capacity = capacity;
    arena->offset = 0;
    arena->prev_offset = 0;
    return true;
}

/**
 * Operasi Alokasi Deterministik O(1) dengan Bitwise Alignment.
 */
void *arena_alloc_aligned(MemoryArena *arena, size_t size, size_t alignment) {
    if (!arena || !arena->buffer || size == 0) return NULL;

    /* Pastikan alignment adalah kelipatan pangkat dua (power of two) */
    assert((alignment != 0) && ((alignment & (alignment - 1)) == 0));

    uintptr_t current_addr = (uintptr_t)arena->buffer + arena->offset;
    uintptr_t aligned_addr = (current_addr + (alignment - 1)) & ~(alignment - 1);
    size_t padding = aligned_addr - current_addr;

    if (arena->offset + padding + size > arena->capacity) {
        /* Out of Memory pada Arena - Tidak dapat memperluas secara silent */
        return NULL;
    }

    arena->prev_offset = arena->offset;
    arena->offset += padding + size;

    void *allocated_memory = (void *)aligned_addr;
    /* Inisialisasi memori ke zero untuk menjaga determinisme */
    memset(allocated_memory, 0, size);
    return allocated_memory;
}

void *arena_alloc(MemoryArena *arena, size_t size) {
    return arena_alloc_aligned(arena, size, DEFAULT_ALIGNMENT);
}

/**
 * Reset Massal: Membebaskan seluruh memori secara instan O(1).
 */
void arena_reset(MemoryArena *arena) {
    if (!arena) return;
    arena->offset = 0;
    arena->prev_offset = 0;
}

/**
 * Deallokasi kernel virtual memory.
 */
void arena_destroy(MemoryArena *arena) {
    if (!arena || !arena->buffer) return;
    munmap(arena->buffer, arena->capacity);
    arena->buffer = NULL;
    arena->capacity = 0;
    arena->offset = 0;
    arena->prev_offset = 0;
}

/* ---------------- Demonstrasi Penggunaan Produksi ---------------- */

typedef struct PacketTelemetry {
    uint64_t timestamp_ns;
    uint32_t session_id;
    uint16_t payload_len;
    uint8_t  flags;
    char     payload[37]; /* Berukuran ganjil untuk menguji penataan alignment */
} PacketTelemetry;

int main(void) {
    MemoryArena arena;
    const size_t ARENA_SIZE = 4 * 1024 * 1024; /* 4 MiB Pre-allocated Pool */

    if (!arena_init(&arena, ARENA_SIZE)) {
        fprintf(stderr, "Gagal mengalokasikan Arena via mmap\n");
        return EXIT_FAILURE;
    }

    printf("Arena berhasil dialokasikan pada basis: %p, Kapasitas: %zu Byte\n",
           (void*)arena.buffer, arena.capacity);

    /* Simulasi pemrosesan paket jaringan latensi rendah tanpa malloc individual */
    for (int frame = 0; frame < 3; ++frame) {
        printf("\n--- Memproses Transaksi Jaringan Frame %d ---\n", frame);

        /* Alokasi array telemetry */
        PacketTelemetry *pkt = (PacketTelemetry *)arena_alloc_aligned(&arena, sizeof(PacketTelemetry), 64);
        if (!pkt) {
            fprintf(stderr, "Arena OOM!\n");
            break;
        }

        pkt->timestamp_ns = 1718000000ULL + frame;
        pkt->session_id = 998244353;
        pkt->payload_len = 12;
        snprintf(pkt->payload, sizeof(pkt->payload), "HEARTBEAT_%d", frame);

        printf("Alokasi Packet %d pada: %p (Current Offset Arena: %zu Byte)\n",
               frame, (void*)pkt, arena.offset);

        /* Simulasi alokasi dinamis sementara dalam siklus transaksi */
        char *request_log = (char *)arena_alloc(&arena, 128);
        snprintf(request_log, 128, "LOG: Packet from session %u processed successfully.", pkt->session_id);
        printf("Log Buffer pada : %p (Current Offset Arena: %zu Byte)\n",
               (void*)request_log, arena.offset);

        /* Transaksi selesai: Reset Arena seketika tanpa overhead munmap/free */
        arena_reset(&arena);
        printf("Arena di-reset. Offset dikembalikan ke: %zu\n", arena.offset);
    }

    arena_destroy(&arena);
    return EXIT_SUCCESS;
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: High-Frequency Trading (HFT) Matching Engine Gateway
**Konstruksi Masalah**:
Sebuah perusahaan sekuritas memproses hingga 5.000.000 pesanan per detik (*order/sec*). Arsitektur lama menggunakan `malloc()` dan `free()` standar glibc dalam *hot-path* penerimaan protokol FIX (*Financial Information eXchange*).

**Gejala Degradasi**:
- Terjadi lonjakan latensi p99.9 (*tail latency spikes*) sebesar 18.000 nanodetik (18 $\mu s$).
- Penyebab: *Thread lock contention* di dalam `ptmalloc` dan fragmentasi memori (*heap fragmentation*) yang memaksa CPU melakukan *TLB Cache Eviction* terus-menerus.

**Solusi Rekayasa Berbasis C**:
1. Menghilangkan alokasi dinamis runtime secara absolut (*Zero-Allocation Pattern*).
2. Membangun model memori berlapis:
   - **Per-Core Static Arena Allocator**: Ditempatkan pada memori NUMA-local node terisolasi via `numa_alloc_onnode()`.
   - **Fixed-Size SPSC Lock-Free Ring Buffer**: Menggunakan pointer atomic berbasis C11 (`stdatomic.h`) dengan *cache-line padding* 64-byte untuk memitigasi isu *False Sharing*.
   - Mengompilasi kode menggunakan `-O3 -march=native -fstrict-aliasing -fno-omit-frame-pointer`.

**Hasil Pengukuran Produksi**:
- Latensi p99.9 terkompresi dari **18 $\mu s$** menjadi **420 nanodetik** ($0.42 \mu s$).
- Fragmentasi memori turun menjadi **0%**.
- Penggunaan CPU berkurang 22% karena penghapusan *trapping* locking glibc.

---

## 9. Trade-offs

| Pendekatan / Pola | Keuntungan (*Pros*) | Kerugian & Batasan (*Cons*) |
| :--- | :--- | :--- |
| **Arena (Bump) Allocator** | Alokasi berkecepatan $O(1)$ mutlak (hanya penambahan pointer); pembersihan massal $O(1)$; fragmentasi internal minimal; data terlokalisasi dalam cache CPU. | Tidak mendukung dealokasi individual per-objek; rentan terjadi pemborosan ruang jika ada satu siklus operasi yang meminta memori terlalu besar dan tidak pernah direset. |
| **Fixed-Size Free List Pool** | Alokasi dan dealokasi individual $O(1)$; fragmentasi nol karena semua blok berukuran homogen. | Kaku (*inflexible*); hanya mendukung alokasi dengan ukuran objek yang identik atau dibatasi oleh *max chunk size*. |
| **Glibc Standard `malloc()`** | Sangat fleksibel; mengelola berbagai variasi ukuran data; mendukung optimasi memori dinamis OS otomatis. | Variansi latensi tinggi (*non-deterministic*); rentan fragmentasi heap jangka panjang; overhead metadata minimal 8–16 byte per chunk. |
| **Stack Allocation (`alloca`)** | Ekstrem cepat (hanya manipulasi register `%rsp`). | Ukuran dibatasi kuota stack OS (biasanya 8MB); jika terjadi *stack overflow* program langsung di-kill oleh *kernel fault* tanpa penanganan *graceful*. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Pointer Arithmetic Pitfall: Tipe Dasar vs Byte Offset
*Kesalahan Kritis*: Melakukan aritmatika offset menggunakan tipe pointer dasar, bukan `uintptr_t` atau `uint8_t*`.

```c
// CACAT LOGIKA
int32_t *array = malloc(10 * sizeof(int32_t));
// Niat: Menggeser sejauh 4 byte (1 elemen)
// Realitas: Menggeser sejauh (4 * sizeof(int32_t)) = 16 byte! Terjadi Out-Of-Bounds!
int32_t *next = array + 4; 

// IMPLEMENTASI AMAN & BENAR
int32_t *correct_next = array + 1; // Lompat 1 elemen int32_t
// Atau jika bekerja dengan raw byte offset:
uint8_t *byte_ptr = (uint8_t*)array;
int32_t *explicit_next = (int32_t*)(byte_ptr + 4);
```

### 10.2 Strict Aliasing Violation
*Kesalahan Fatal*: Tipe *Type-Punning* yang melanggar standar ANSI/ISO C.

```c
// CACAT (Mematahkan optimasi kompilator & memicu Undefined Behavior)
float value = 5.5f;
uint32_t *raw_bits = (uint32_t*)&value; // UB! Pelanggaran Strict Aliasing
printf("Bits: %u\n", *raw_bits);

// CARA BENAR PRODUKSI (Menggunakan memcpy atau Union type punning)
float value_safe = 5.5f;
uint32_t raw_bits_safe;
memcpy(&raw_bits_safe, &value_safe, sizeof(raw_bits_safe)); // Kompilator mengoptimalkan ini ke register move (0 instruction overhead)
```

### 10.3 False Sharing pada Multi-threaded Memory Structures
Ketika dua thread pada inti CPU yang berbeda memodifikasi variabel berbeda yang berada di dalam satu *Cache Line* (64-byte) yang sama, CPU saling membatalkan baris cache (*cache invalidation*), memicu penurunan performa drastis hingga 90%.

*Penyelesaian*: Gunakan instruksi penyelarasan batas *cache-line*:
```c
#include <stdalign.h>

struct WorkerState {
    alignas(64) uint64_t thread_1_counter; // Berada di cache-line independen
    alignas(64) uint64_t thread_2_counter; // Aman dari false sharing
};
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Kompilasi dengan Strict Diagnostic Flags**:
  Wajib mengaktifkan: `-Wall -Wextra -Wpedantic -Werror -Wconversion -Wshadow -Wformat=2 -Wundef`.
- [ ] **Inkorporasikan Sanitizer Pipeline di Tahap CI/CD**:
  Lakukan pengetesan dengan opsi sanitasi aktif:
  ```bash
  gcc -fsanitize=address,undefined -fno-omit-frame-pointer -g -O1 source.c -o test_bin
  ```
- [ ] **Desain Struktur untuk Cache Line Packing**:
  Urutkan anggota struktur secara menurun: `uint64_t` -> `uint32_t` -> `uint16_t` -> `uint8_t` untuk meniadakan struktur *implicit padding*.
- [ ] **Terapkan Paradigma Opaque Pointer**:
  Sembunyikan detail implementasi struktur internal dari berkas header publik untuk menjamin stabilitas ABI (*Application Binary Interface*):
  ```c
  /* engine.h */
  typedef struct EngineContext EngineContext; // Tipe Buram (Opaque)
  EngineContext* engine_create(void);
  void engine_destroy(EngineContext *ctx);
  ```
- [ ] **Gunakan `volatile` Hanya untuk Memory-Mapped I/O Hardware**:
  Jangan pernah gunakan `volatile` untuk sinkronisasi multithreading; gunakan C11 `<stdatomic.h>`.
- [ ] **Hardening Binary Security Flags**:
  Terapkan proteksi biner di level linker: `-Wl,-z,relro,-z,now` (Full RELRO), `-fstack-protector-strong`, serta pastikan stack dieksekusi dengan `-Wl,-z,noexecstack`.

---

## 12. Hands-on Practice

Dalam sesi praktikum ini, Anda akan membedah berkas ELF, menguji pelanggaran *segmentation fault*, serta memvalidasi alinyemen data.

### Langkah Praktikum: Implementasi dan Eksplorasi Low-Level
Simpan seluruh pekerjaan pada folder `hands-on/m02/`.

#### Langkah 1: Buat Berkas `hands-on/m02/elf_layout.c`
```c
#include <stdio.h>
#include <stdlib.h>

const int GLOBAL_CONST = 100;
int global_bss_array[1024 * 1024]; // 1 Juta Integer di BSS

int main(void) {
    printf("Base program pointer: %p\n", (void*)main);
    return 0;
}
```

#### Langkah 2: Inspeksi Binary Footprint pada Disk
Jalankan perintah shell berikut:
```bash
mkdir -p hands-on/m02/
gcc -O0 -g hands-on/m02/elf_layout.c -o hands-on/m02/elf_layout
ls -lh hands-on/m02/elf_layout
size hands-on/m02/elf_layout
```
*Observasi*: Perhatikan ukuran biner pada disk (~15-20 KB), padahal variabel `global_bss_array` memakan ruang 4 MB! Periksa kolom `bss` pada luaran utilitas `size`.

#### Langkah 3: Ekstraksi Seksi Menggunakan `readelf` dan `objdump`
```bash
readelf -S hands-on/m02/elf_layout
objdump -t hands-on/m02/elf_layout | grep global_
```
*Tugas Analisis*: Temukan *Virtual Address* offset di mana `GLOBAL_CONST` ditempatkan (`.rodata`) dan amati perbedaan benderanya (*Flags*: `WA` untuk BSS vs `A` untuk Rodata).

---

## 13. Exercise

### Level Easy
Modifikasi implementasi struktur data di bawah ini agar ukurannya mengecil ke batas minimal teoritis menggunakan penataan field manual (bukan `#pragma pack`). Uji perubahannya menggunakan operator `sizeof()`.

```c
struct SensorNode {
    uint8_t  node_id;
    uint64_t uptime_seconds;
    uint8_t  status_flag;
    uint32_t ip_address;
    uint16_t port;
};
```
*Kunci Verifikasi*: Ukuran awal kemungkinan 24 byte. Target optimal adalah 16 byte.

### Level Medium
Kembangkan fungsi utilitas string replacement dalam bahasa C:
```c
char *safe_string_replace(MemoryArena *arena, const char *orig, const char *rep, const char *with);
```
*Batasan Operasi*:
- Dilarang memanggil `malloc`, `calloc`, atau `realloc`.
- Seluruh kebutuhan memori harus diambil dari instans `MemoryArena` (dari contoh implementasi di Bab 7.2).
- Harus memproses teks dalam satu pass alokasi (*single-pass sizing*) untuk menghindari alokasi berlebih di dalam arena.

### Level Hard
Bangun implementasi **Fixed-Size Object Pool Allocator (Free List Pool)** berkinerja tinggi dengan spesifikasi teknis:
1. `pool_init(Pool *p, size_t object_size, size_t capacity)`: Mengalokasikan seluruh blok memori di awal.
2. `pool_alloc(Pool *p)`: Mengembalikan satu slot kosong dalam operasi deterministik $O(1)$. Manfaatkan memori dari node kosong itu sendiri untuk menyimpan pointer `next` (*Intrusive Free List*), sehingga tidak memerlukan alokasi memori tambahan untuk metadata pelacakan!
3. `pool_free(Pool *p, void *ptr)`: Mengembalikan slot memori ke dalam daftar free-list dalam $O(1)$.
4. Aman dari fragmentasi eksternal.

---

## 14. Challenge

### Studi Kasus: Autonomous Telemetry Engine Crash Investigation
Sebuah subsistem telemetri pesawat nirawak mengalami crash acak (*intermittent SIGSEGV*) setelah berjalan kontinu selama 72 jam. Setelah dilakukan *core-dump extraction* melalui GDB, ditemukan pola kegagalan berikut:

```
Program terminated with signal SIGSEGV, Segmentation fault.
#0  0x000000000040189a in ring_buffer_push (rb=0x7ffe102a, telemetry_data=0x7ffe10a0)
    at flight_telemetry.c:88
88      rb->entries[rb->head & (rb->capacity - 1)] = *telemetry_data;
(gdb) print rb->capacity
$1 = 1000
(gdb) print rb->head
$2 = 1024
```

**Spesifikasi Tantangan**:
1. Bedah secara matematis dan arsitektural mengapa ekspresi `rb->head & (rb->capacity - 1)` memicu bencana korupsi memori (*memory corruption*) atau *out-of-bounds access* ketika kapasitasnya bernilai 1000!
2. Rancang ulang implementasi *Ring Buffer* tersebut agar:
   - Aman dari jebakan kalkulasi non-power-of-two (berikan validasi kompilasi atau runtime *assertion*).
   - Memiliki keselarasan *cache-line* (bebas dari *false sharing* antara pointer `head` yang diakses *Producer Core* dan pointer `tail` yang diakses *Consumer Core*).
   - Menyertakan mekanisme *fail-safe* jika terjadi *buffer overrun* tanpa menjatuhkan proses utama.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda / Analisis Singkat)
1. Di segmen memori manakah variabel lokal yang dialokasikan di dalam fungsi tanpa kata kunci `static` disimpan?
   - A. Heap
   - B. BSS
   - C. Stack
   - D. Data
2. Berapakah ukuran byte fisik yang terbuang pada berkas biner di *disk* penyimpanan untuk sebuah array global tak-terinisialisasi `uint8_t buffer[1048576]` yang berada di segmen `.bss`?
   - A. Tepat 1 MB
   - B. Sekitar 0 Byte (hanya tercatat ukuran metadata di tabel seksi ELF)
   - C. Tergantung kapasitas RAM sistem
   - D. 4 MB karena paging
3. Apa implikasi instruksi perakitan mesin (*assembly instruction*) saat fungsi memanggil variabel bertipe `const char *s = "ABC";` jika kode mencoba mengubah `s[0] = 'Z';`?
   - A. Karakter berubah tanpa komplikasi
   - B. Kompilator mengubahnya otomatis menjadi static char array
   - C. CPU memicu *General Protection Fault* yang menghasilkan *SIGSEGV*
   - D. Data terhapus dari heap
4. Register x86_64 ABI mana yang digunakan untuk menampung argumen pointer/integer pertama pada pemanggilan fungsi?
   - A. `%rax`
   - B. `%rsp`
   - C. `%rbp`
   - D. `%rdi`
5. Berapakah batas *memory alignment* alami (*natural alignment*) untuk variabel berjenis pointer 64-bit pada arsitektur target x86_64?
   - A. 2-byte
   - B. 4-byte
   - C. 8-byte
   - D. 16-byte

### Bagian 2: Intermediate (Analisis Kasus & Algoritma)
1. Jelaskan mengapa pemanggilan `memset(ptr, 0, sizeof(ptr))` sering kali merupakan *bug* mematikan jika `ptr` didefinisikan sebagai pointer yang menerima alokasi array dinamis via `malloc(100 * sizeof(int))`!
2. Apa tujuan penggunaan flag `-fno-omit-frame-pointer` pada sistem produksi skala besar, dan apa hubungannya dengan penelusuran *stack unwinding* oleh profiler modern (seperti Linux `perf` atau eBPF)?
3. Jelaskan perbedaan mendasar mekanisme *demand-zero paging* pada alokasi anonim via `mmap()` dibandingkan alokasi stack konvensional!
4. Diberikan kode:
   ```c
   void compute(int * restrict a, int * restrict b, int * restrict c, size_t n) {
       for (size_t i = 0; i < n; ++i) {
           *a += *c;
           *b += *c;
       }
   }
   ```
   Bagaimana kata kunci `restrict` mengubah instruksi perakitan mesin yang di-generate kompilator pada pembacaan `*c` di dalam loop tersebut?
5. Jelaskan bahaya tersembunyi dari makro pembersih memori berikut jika kompilator melakukan optimasi tingkat tinggi (`-O3`):
   ```c
   void erase_credentials(char *token, size_t len) {
       memset(token, 0, len);
   }
   ```
   Bagaimana standar C11 mengatasi ancaman ini?

### Bagian 3: Skenario Kasus Produksi
1. **Skenario Masalah A (Deadlock on Allocation)**: Sebuah modul C multithreaded yang bertugas memproses data streaming performa tinggi menggunakan pustaka `glibc ptmalloc`. Saat beban sistem mencapai 80.000 transaksi/detik, penggunaan CPU melonjak 100%, namun throughput jatuh mendekati nol. Analisis via `gdb` menunjukkan sebagian besar thread berhenti pada fungsi `__lll_lock_wait_private` di dalam `malloc()`. Bagaimana Anda mendiagnosis akar masalah ini dan arsitektur alokasi apa yang harus diterapkan untuk menyelesaikannya?
2. **Skenario Masalah B (Silent Memory Corruption via Aliasing)**: Sebuah mesin kalkulasi matriks mengalami galat matematis yang tidak menentu hanya saat dikompilasi dengan parameter `-O3`, namun kalkulasi berjalan 100% akurat saat dikompilasi dengan `-O0`. Jelaskan metodologi Anda untuk mengisolasi potensi pelanggaran *Strict Aliasing Rules*, dan sebutkan flag kompilasi apa yang dapat digunakan sebagai verifikasi awal!
3. **Skenario Masalah C (Memory Footprint Bloat)**: Tim infrastruktur mendapati bahwa layanan pemrosesan batch biner C yang berjalan di Kubernetes mengalami *OOMKilled* (Out Of Memory Killed oleh OS Kernel). Profiling menunjukkan ukuran alokasi virtual (`VIRT`) terus membesar, namun memori residen aktual (`RES`) yang aktif terpakai jauh di bawah ambang batas pod. Selidiki bagaimana fragmentasi memori heap glibc atau perilaku alokasi `mmap` vs `brk` memicu disparitas ini, dan bagaimana konfigurasi `MALLOC_ARENA_MAX` mempengaruhinya!

---

## 16. Summary

1. **Pemahaman Segmentasi Memori Adalah Fondasi Performa**: Menguasai interaksi antara kode C, format biner ELF, memori virtual, dan register arsitektur (ABI) adalah pembeda utama antara rekayasawan tingkat dasar dan perancang sistem enterprise.
2. **Deterministik Lebih Unggul daripada Generik**: Alokasi `malloc()` standar glibc didesain untuk kebutuhan umum, bukan performa ekstrem. Pola manajemen memori kustom seperti *Arena Allocator* dan *Fixed-Size Object Pool* memangkas latensi alokasi menjadi $O(1)$, menjamin pemanfaatan cache CPU secara optimal, dan mengeliminasi fragmentasi.
3. **Penyelarasan Data Menentukan Efisiensi Hardware**: Struktur data harus dirancang dengan memperhatikan *natural alignment* dan *cache line boundaries* (64-byte) untuk mencegah penalti siklus CPU, *unaligned access*, dan isu multithreading *False Sharing*.
4. **Keamanan Produksi Melalui Toolchain Ketat**: Kode produksi wajib diverifikasi menggunakan suite sanitasi modern (`ASan`, `UBSan`), memanfaatkan kata kunci ketat (`restrict`, `const`), serta menerapkan pengerasan tautan biner (*Full RELRO*, *No-Executable Stack*). Praktik ini memastikan kode C beroperasi secara tangguh, deterministik, dan aman pada lingkungan skala enterprise.