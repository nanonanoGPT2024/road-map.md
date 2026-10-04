# KURIKULUM REKAYASA PERANGKAT LUNAK SISTEM: C ENTERPRISE
## BAB 05: Array, String Idiom & Zero-Copy Buffer Processing
### MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis dan Memitigasi Cache Invalidation & Page Faults:** Memahami interaksi antara struktur array contiguous, memory controller, translation lookaside buffer (TLB), dan L1/L2/L3 data cache pada arsitektur x86_64 dan AArch64.
- **Mengimplementasikan Zero-Copy Parsing Engine:** Membangun parser string dan biner performa tinggi berbasis *String View* (*slice primitives*) dan pointer sliding window tanpa memanggil alokasi heap repetitif (`malloc`/`free`).
- **Mendesain Ring Buffer Lock-Free Single-Producer Single-Consumer (SPSC):** Mengimplementasikan circular ring buffer thread-safe berbasis memory barrier dan cache-line padding untuk transmisi buffer streaming berlatensi sub-mikrodetik.
- **Mengoptimalkan I/O melalui Scatter-Gather dan Memory-Mapped I/O:** Mengonfigurasi `readv`/`writev` (*vectored I/O*) dan `mmap` untuk memproses payload jaringan/disk langsung dari memory map kernelspace ke userspace tanpa intermediate copy.
- **Mendeteksi Memory Corruption & Undefined Behavior:** Menggunakan compiler flags mutakhir (`-fsanitize=address,undefined`), static analysis, serta valgrind untuk mendeteksi off-by-one, pointer aliasing hazard, dan heap/stack buffer overflows.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, engineer wajib menguasai:
- **Bahasa Pemrograman C Tingkat Dasar & Menengah:** Paham sintaksis pointer dereferencing, arithmetic pointer, casting generic pointer (`void *`), serta struct memory layout (alignment dan padding).
- **Konsep Sistem Operasi & Arsitektur Komputer:** Memahami virtual memory, paging, system call transitions (context switch), dan hirarki memori hardware (Register $\rightarrow$ L1 $\rightarrow$ L2 $\rightarrow$ L3 $\rightarrow$ DRAM).
- **Tooling Lingkungan Linux:** Menguasai penggunaan `gcc` / `clang`, `gdb`, `strace`, serta environment terminal POSIX.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Anatomi Memori Contiguous dan Hardware Cache Interaction
Array pada C direpresentasikan sebagai blok virtual memory contiguous berukuran `N * sizeof(T)`. Pada arsitektur modern, CPU tidak pernah mengambil satu byte data langsung dari DRAM, melainkan dalam satuan **Cache Line** (umumnya 64 byte pada arsitektur x86_64 dan modern ARM).

```
DRAM Memory Address Space:
[ Byte 0x00 ........................................ Byte 0x3F ]  <-- 64-Byte Cache Line 0
[ Byte 0x40 ........................................ Byte 0x7F ]  <-- 64-Byte Cache Line 1
```

Ketika proses membaca elemen array pertama `arr[0]`, CPU Hardware Prefetcher memuat seluruh 64 byte blok memori tersebut ke L1 Data Cache (L1D). 
- **Spatial Locality:** Iterasi sekuensial (stride-1 traversal) memaksimalkan cache hits karena elemen berikutnya (`arr[1]`, `arr[2]`, dst.) sudah tersedia di L1 cache latency (~1 ns atau 4 clock cycles).
- **False Sharing:** Apabila dua thread pada core CPU berbeda mengakses variabel terpisah yang kebetulan berada dalam satu cache line 64-byte yang sama, protokol cache coherence (misal: MESI/MOESI) akan memaksa invalidasi cache antar core. Hal ini merusak throughput konkurensi secara signifikan.

#### 3.2 Deadlocks Paradigma Tradisional: Copy-Heavy vs Zero-Copy
Dalam paradigma klasik string/buffer handling (seperti `strcpy`, `strcat`, `strdup`), parsing protokol berorientasi pesan (misal: HTTP, FIX Protocol, gRPC framing) menduplikasi data berkali-kali:

```
[Network Card (NIC)] 
       │ (DMA Transfer)
[Kernel Socket Buffer (sk_buff)] 
       │ (sys_read() / context switch / CPU copy)
[Userspace Staging Buffer] 
       │ (Tokenizing / malloc / strcpy)
[Application Object Buffer]
```

Paradigma **Zero-Copy Memory Slicing** mengeliminasi salinan data antara staging buffer dan entitas bisnis. Sebagai gantinya, token representasi cukup berupa pointer offset ke buffer asli ditambah panjang data (`length`).

#### 3.3 Anatomi String View / Buffer Slice Primitives
String standar C berbasis *null-terminated string* (`\0`) mewajibkan mutasi buffer (in-place replacement byte pemisah dengan `\0`) atau alokasi buffer baru via `malloc` jika data asli bersifat read-only. Desain enterprise menggunakan *explicit-length string view*:

```c
typedef struct {
    const char *data;  // Pointer ke memori buffer yang sudah ada (tidak memiliki ownership)
    size_t len;        // Ukuran segmen dalam byte
} string_view_t;
```

Keuntungan arsitektur ini:
1. Operasi slicing bersifat $O(1)$ waktu dan memori (tidak ada alokasi heap).
2. Sub-string dapat menunjuk ke payload read-only (`.rodata`, mapped file read-only).
3. Payload biner yang mengandung byte `0x00` tetap valid dan tidak memotong string.

#### 3.4 Scatter-Gather I/O (`struct iovec`)
Ketika data tersebar di berbagai region memori non-contiguous (misal: HTTP header di stack, body payload di memory-mapped file), I/O tradisional membutuhkan penggabungan buffer (merging via `memcpy`). Dengan interface POSIX Scatter-Gather (`readv(2)` / `writev(2)`):

$$\text{Total Bytes Transferred} = \sum_{i=0}^{iov\_cnt - 1} iov[i].iov\_len$$

Kernel mengonsumsi array `struct iovec` dan langsung mengirimkannya ke socket buffer melalui satu system call tunggal, mereduksi CPU overhead dan cache pollution.

---

### 4. Why & What

| Dimensi | Pendekatan Tradisional (Naive C Buffer) | Pendekatan Enterprise Zero-Copy |
| :--- | :--- | :--- |
| **Representasi String** | Null-terminated (`char *` diakhiri `\0`) | Fat pointer / Slice (`ptr` + `len`) |
| **Alokasi Token** | `malloc` / `strdup` untuk tiap field | Tidak ada alokasi baru (Window Sliding) |
| **Kompleksitas Substring** | $\mathcal{O}(N)$ waktu, $\mathcal{O}(N)$ memori | $\mathcal{O}(1)$ waktu, $\mathcal{O}(1)$ memori |
| **I/O Strategy** | `read`/`write` per-buffer loop | Vectored I/O (`writev`) atau Ring Buffer |
| **Memory Access Pattern** | Arbitrary pointer hops (Fragmented) | Contiguous linear streaming (Cache friendly) |
| **CPU Cache Pressure** | Tinggi (Polusi L1/L2 karena duplikasi data) | Rendah (Hanya referensi indeks yang berubah) |

---

### 5. How (Workflow & Algoritma Zero-Copy Parsing)

Workflow parsing zero-copy streaming:

```
[ Inbound Packet (NIC/Socket) ]
              │
              ▼
[ Fixed-size Ring Buffer (Pre-allocated) ]
              │
              ├─ Pointer Calculation (Scanning Delimiter: '\r\n')
              │  (Menggunakan SIMD / memchr)
              │
              ▼
[ Extract `string_view_t` (Slice: data = ptr, len = delta) ]
              │
              ▼
[ Pass Slice directly to Router / Business Handler ]
              │
              ▼
[ Shift Read Cursor of Ring Buffer ]
```

1. **Pre-alokasi:** Inisialisasi linear contiguous buffer kapasitas besar di awal (ring buffer atau arena memory). Tidak boleh ada alokasi runtime pada path pemrosesan data (hot path).
2. **Scan Tanpa Modifikasi:** Gunakan pemindaian berbasis batas (`memchr`, SIMD vector scan). Jangan gunakan `strtok` karena memodifikasi byte input (`\0`) dan bersifat stateful (non-reentrant).
3. **Konstruksi Slice:** Kembalikan struktur slice. Jika string view perlu divalidasi sebagai integer, gunakan fungsi non-null-terminated custom parser (misal: custom parse unsigned int) untuk mencegah kebutuhan copy data.

---

### 6. Analogy & Diagram ASCII

#### Analogi Perpustakaan Dokumen Fisik
- **Naive Buffer Strategy:** Setiap kali seorang analis meminta kutipan bab tertentu dari arsip tebal, staf fotokopi menduplikasi bab tersebut ke lembaran kertas baru, lalu menyerahkannya. Hasilnya: kertas menumpuk, energi terbuang, printer lambat.
- **Zero-Copy String View:** Staf perpustakaan hanya memberikan kartu indeks transparan yang mencatat: *“Buku Induk A, Halaman 45, Baris 12 hingga Baris 80”*. Analis membaca langsung dari buku induk aslinya. Tidak ada kertas baru yang dicetak, tidak ada resource yang terbuang.

#### Diagram Arsitektur Memory-Mapped Zero-Copy Ring Buffer
```
               Cache Line 1 (64 Bytes)             Cache Line 2 (64 Bytes)
         ┌───────────────────────────────────┬───────────────────────────────────┐
Memory:  │ [Head Index]  [Padding: 56 Bytes] │ [Tail Index]  [Padding: 56 Bytes] │
         └───────────────────────────────────┴───────────────────────────────────┘
                           │                                   │
                           ▼                                   ▼
                   Produced Data Read                  Consumed Data Read
             (CPU Core 0 Cache: Inbound)        (CPU Core 1 Cache: Processing)

Ring Array Data Space:
┌───────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┐
│ Chunk │ Chunk │ Chunk │ Chunk │ Chunk │ Chunk │ Chunk │ Chunk │
│   0   │   1   │   2   │   3   │   4   │   5   │   6   │   7   │
└───────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┘
  ▲                       ▲
  │                       │
  Tail (Consumer)         Head (Producer)
  [==== Read Valid Area ==]
```

---

### 7. Implementasi Kode Teruji Standar Industri

#### 7.1 Implementasi String View & Tokenizer Non-Destruktif
Kode berikut mengimplementasikan `string_view` modern beserta helper hashing cepat (djb2) dan parser numerik tanpa ketergantungan `\0`.

```c
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>

typedef struct {
    const char *data;
    size_t len;
} string_view_t;

#define SV(cstr) ((string_view_t){ .data = (cstr), .len = strlen(cstr) })
#define SV_STATIC(literal) ((string_view_t){ .data = "" literal "", .len = sizeof(literal) - 1 })

static inline bool sv_equals(string_view_t a, string_view_t b) {
    if (a.len != b.len) return false;
    return memcmp(a.data, b.data, a.len) == 0;
}

static inline bool sv_starts_with(string_view_t sv, string_view_t prefix) {
    if (sv.len < prefix.len) return false;
    return memcmp(sv.data, prefix.data, prefix.len) == 0;
}

static inline string_view_t sv_slice(string_view_t sv, size_t start, size_t end) {
    assert(start <= end && end <= sv.len);
    return (string_view_t){
        .data = sv.data + start,
        .len = end - start
    };
}

// Tokenizer non-destruktif: Memotong string view berdasarkan karakter delimiter
static bool sv_split_step(string_view_t *source, char delimiter, string_view_t *token) {
    if (source->len == 0) {
        return false;
    }

    const char *delim_pos = memchr(source->data, delimiter, source->len);
    if (delim_pos != NULL) {
        size_t token_len = (size_t)(delim_pos - source->data);
        token->data = source->data;
        token->len = token_len;

        source->data = delim_pos + 1;
        source->len = source->len - (token_len + 1);
    } else {
        token->data = source->data;
        token->len = source->len;

        source->data += source->len;
        source->len = 0;
    }
    return true;
}

// Konversi string_view ke uint64_t tanpa alokasi / strtoull dependence
static bool sv_to_u64(string_view_t sv, uint64_t *out_val) {
    if (sv.len == 0) return false;
    uint64_t result = 0;
    for (size_t i = 0; i < sv.len; ++i) {
        char c = sv.data[i];
        if (c < '0' || c > '9') return false;
        
        uint64_t prev = result;
        result = result * 10 + (uint64_t)(c - '0');
        if (result < prev) return false; // Overflow check
    }
    *out_val = result;
    return true;
}

int main(void) {
    // Inbound raw network line buffer (Contoh HTTP Header)
    const char raw_packet[] = "Host: api.internal.enterprise\r\nContent-Length: 4096\r\nX-Forwarded-For: 10.0.0.1";
    string_view_t packet_view = { .data = raw_packet, .len = sizeof(raw_packet) - 1 };

    string_view_t line;
    printf("[*] Memulai Zero-Copy Parsing Header...\n");

    while (sv_split_step(&packet_view, '\n', &line)) {
        // Strip trailing '\r' jika ada
        if (line.len > 0 && line.data[line.len - 1] == '\r') {
            line.len--;
        }

        string_view_t key, val = line;
        if (sv_split_step(&val, ':', &key)) {
            // Trim leading space pada value
            while (val.len > 0 && val.data[0] == ' ') {
                val.data++;
                val.len--;
            }

            printf("Parsed Field -> Key: '%.*s', Value: '%.*s'\n",
                   (int)key.len, key.data,
                   (int)val.len, val.data);

            if (sv_equals(key, SV("Content-Length"))) {
                uint64_t clen = 0;
                if (sv_to_u64(val, &clen)) {
                    printf("  --> Extracted Content-Length as Integer: %lu\n", (unsigned long)clen);
                }
            }
        }
    }
    return 0;
}
```

#### 7.2 Implementasi Cache-Aligned SPSC Lock-Free Circular Ring Buffer
Implementasi buffer berkinerja tinggi untuk sistem trading atau telemetri dengan pemisahan cache line untuk producer dan consumer.

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <string.h>

#define CACHE_LINE_SIZE 64
#define RING_BUFFER_CAPACITY 1024 // Wajib power-of-two (2^N)

typedef struct {
    uint64_t sequence;
    uint32_t payload_len;
    uint8_t  payload[256];
} ring_item_t;

typedef struct {
    // Producer State - Cache Line Isolated
    alignas(CACHE_LINE_SIZE) _Atomic size_t head;
    uint8_t pad1[CACHE_LINE_SIZE - sizeof(_Atomic size_t)];

    // Consumer State - Cache Line Isolated
    alignas(CACHE_LINE_SIZE) _Atomic size_t tail;
    uint8_t pad2[CACHE_LINE_SIZE - sizeof(_Atomic size_t)];

    // Buffer Memory Contiguous
    alignas(CACHE_LINE_SIZE) ring_item_t items[RING_BUFFER_CAPACITY];
} spsc_ring_buffer_t;

void ring_init(spsc_ring_buffer_t *rb) {
    atomic_init(&rb->head, 0);
    atomic_init(&rb->tail, 0);
    memset(rb->items, 0, sizeof(rb->items));
}

// Push item (Produsen tunggal)
bool ring_enqueue(spsc_ring_buffer_t *rb, const ring_item_t *src) {
    size_t current_head = atomic_load_explicit(&rb->head, memory_order_relaxed);
    size_t current_tail = atomic_load_explicit(&rb->tail, memory_order_acquire);

    // Cek apakah buffer penuh (Capacity - 1 untuk membedakan full dan empty)
    if ((current_head - current_tail) >= RING_BUFFER_CAPACITY) {
        return false; // Queue Penuh
    }

    // Index wrapping optimal via bitwise AND (karena capacity 2^N)
    size_t index = current_head & (RING_BUFFER_CAPACITY - 1);
    
    // Copy data ke slot
    rb->items[index] = *src;

    // Release fence menjamin transfer data selesai sebelum head di-expose
    atomic_store_explicit(&rb->head, current_head + 1, memory_order_release);
    return true;
}

// Pop item (Konsumen tunggal)
bool ring_dequeue(spsc_ring_buffer_t *rb, ring_item_t *dst) {
    size_t current_tail = atomic_load_explicit(&rb->tail, memory_order_relaxed);
    size_t current_head = atomic_load_explicit(&rb->head, memory_order_acquire);

    // Cek jika antrean kosong
    if (current_tail == current_head) {
        return false;
    }

    size_t index = current_tail & (RING_BUFFER_CAPACITY - 1);
    *dst = rb->items[index];

    atomic_store_explicit(&rb->tail, current_tail + 1, memory_order_release);
    return true;
}

int main(void) {
    printf("[*] Alignment Ring Buffer: %zu bytes\n", alignof(spsc_ring_buffer_t));
    spsc_ring_buffer_t *rb = aligned_alloc(CACHE_LINE_SIZE, sizeof(spsc_ring_buffer_t));
    assert(rb != NULL);

    ring_init(rb);

    ring_item_t item_in = {
        .sequence = 1001,
        .payload_len = 5,
        .payload = "HELLO"
    };

    if (ring_enqueue(rb, &item_in)) {
        printf("[+] Item Enqueued: Seq %lu\n", item_in.sequence);
    }

    ring_item_t item_out;
    if (ring_dequeue(rb, &item_out)) {
        printf("[+] Item Dequeued: Seq %lu, Payload: %s\n", item_out.sequence, item_out.payload);
    }

    free(rb);
    return 0;
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Domain: Market Data Feed Handler (Financial Ultra-Low Latency Engine)
- **Problem Statement:** Sebuah financial brokerage menerima UDP Multicast stream protokol FAST/ITCH dengan throughput 1.500.000 pesan/detik. Menggunakan sistem lama (`memcpy` tiap packet ke internal parsing struct via `malloc`), sistem sering mengalami latency spike (P99.99 > 850 mikrodetik) akibat Garbage Collection CPU thread (karena heap fragmentation) dan Memory Bus Contention.
- **Root Cause Analysis:** Profiling dengan `perf record -e cache-misses,L1-dcache-load-misses` menunjukkan 34% siklus clock CPU dihabiskan untuk menunggu L1 Data Cache load miss dan stall memori saat eksekusi `memcpy`. Terjadi pointer bouncing antar socket buffer kernel dan userspace structure.
- **Architectural Solution:**
  1. Menggunakan Linux Kernel Bypass (AF_XDP / Solarflare OpenOnload) memetakan inbound ring buffer DMA NIC langsung ke memory space userspace.
  2. Implementasi **Zero-Copy Deserializer**: Membuat frame header parsing yang memetakan struct C typed directly (`struct itch_order_book_update *msg = (const void *)(raw_packet_ptr)`) menggunakan pointer casting yang aman dan verifikasi data alignment.
  3. Menggantikan seluruh field teks kode saham (`char ticker[8]`) dengan string views.
- **Result:** P99.99 Latency turun dari 850µs menjadi **1.8µs**. Memory throughput stabil tanpa alokasi heap (`0 allocs/sec`), utilisasi CPU L1D cache hit rate melonjak dari 66% menjadi 98.4%.

---

### 9. Trade-offs

| Aspek | Naive Copy Strategy | Zero-Copy Slice Primitives |
| :--- | :--- | :--- |
| **Throughput & Bandwidth** | Rendah: Dibatasi oleh bus memory bandwidth ($DRAM \leftrightarrow L3 \leftrightarrow L1$). | Maksimum: Terbatas hanya oleh saturasi I/O bus interface NIC/SSD. |
| **Lifespan Management** | Sederhana: Tiap sub-bagian memiliki copy sendiri; bebas dibersihkan dengan `free()`. | Sangat Kompleks: View tidak boleh hidup melampaui buffer induk (*Dangling Slice*). |
| **Immutability Protection** | Tinggi: Mengubah sub-string tidak memengaruhi buffer asli. | Rendah: Kesalahan penulisan pointer pada buffer asli akan merusak seluruh string view aktif. |
| **Boundary Safety** | Tergantung null byte (`\0`). Rawan buffer overread jika null terhapus. | Deterministik: Panjang tercatat secara eksplisit via `.len`. |

---

### 10. Common Mistakes & Troubleshooting

#### Pitfall 1: Dangling Pointer Akibat Invalidation Buffer Induk
- **Problem:** `string_view` menunjuk ke alamat buffer stack atau heap yang telah di-*reallocate* atau di-*free*.
- **Detection via ASan:** Compile program menggunakan `-fsanitize=address`. AddressSanitizer akan memunculkan error: `AddressSanitizer: heap-use-after-free` atau `stack-use-after-return`.

#### Pitfall 2: Misaligned Pointer Casting
- **Problem:** Membaca integer multi-byte (seperti `uint32_t *` atau `uint64_t *`) langsung dari unaligned offset dalam raw char buffer (`(uint32_t *)(buffer + 3)`).
- **Impact:** Pada arsitektur ARM32/MIPS ini memicu hardware exception `SIGBUS`. Pada arsitektur x86_64 ini memicu unaligned load penalty (2-3x clock cycles latency).
- **Fix:** Gunakan `memcpy` bawaan compiler untuk mengambil nilai skalar unaligned (compiler modern mengoptimalkan `memcpy` unaligned ukuran kecil menjadi satu instruksi `mov` unaligned hardware).
```c
static inline uint32_t read_u32_unaligned(const void *ptr) {
    uint32_t val;
    memcpy(&val, ptr, sizeof(val));
    return val;
}
```

#### Pitfall 3: Mengirim String View ke Fungsi Libc yang Memerlukan Null Terminator
- **Problem:** Mengoper pointer string view ke `printf("%s", sv.data)` atau `atoi(sv.data)`.
- **Impact:** Terjadi *out-of-bounds read* sampai program menemukan byte `0x00` acak di memori, mengakibatkan kebocoran informasi (*data leak*) atau segmentation fault.
- **Fix:** Gunakan format specifier precision: `printf("%.*s", (int)sv.len, sv.data)`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Strict Bounds Boundary Validation:** Selalu validasi bahwa `(offset + length) <= total_capacity` sebelum membuat slice baru. Gunakan pemeriksaan terhadap unsigned underflow/overflow: `offset <= total_capacity && length <= (total_capacity - offset)`.
- [ ] **Explicit Memory Lifetimes:** Dokumentasikan secara ketat kontrak kepemilikan memori (`owner` vs `borrower`). Buffer induk dilarang dimutasi atau dibebaskan selama borrower view masih dalam antrean eksekusi.
- [ ] **Power-of-Two Ring Buffers:** Selalu tentukan kapasitas Circular Ring Buffer sebagai kelipatan $2^N$ sehingga modulus division dapat digantikan operasi bitwise AND (`index & (size - 1)`), mereduksi pembagian siklus ALU dari ~20-40 cycles menjadi 1 cycle.
- [ ] **False Sharing Prevention:** Pisahkan *hot variables* yang ditulis oleh core berbeda ke cache line terpisah menggunakan `alignas(64)` atau padding manual.
- [ ] **No Dynamic Allocation di Hot Path:** Hindari pemanggilan `malloc`, `realloc`, dan `free` di dalam loop streaming packet. Lakukan prealokasi arena atau pool saat booting sistem.

---

### 12. Hands-on Practice

Buat dan navigasikan direktori praktikum berikut:
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

#### Langkah 1: Tulis Implementasi Zero-Copy Parser
Simpan berkas berikut dengan nama `hands-on/m02/zero_copy_log.c`:
```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

typedef struct {
    const char *ptr;
    size_t len;
} log_slice_t;

typedef struct {
    log_slice_t timestamp;
    log_slice_t severity;
    log_slice_t service;
    log_slice_t message;
} parsed_log_entry_t;

bool parse_log_line(const char *raw_line, size_t line_len, parsed_log_entry_t *out_entry) {
    const char *cursor = raw_line;
    const char *end = raw_line + line_len;

    // Format: [TIMESTAMP] [SEVERITY] [SERVICE] MESSAGE
    // 1. Parse TIMESTAMP
    if (cursor >= end || *cursor != '[') return false;
    cursor++;
    const char *token_start = cursor;
    const char *token_end = memchr(cursor, ']', end - cursor);
    if (!token_end) return false;
    out_entry->timestamp = (log_slice_t){ .ptr = token_start, .len = (size_t)(token_end - token_start) };
    cursor = token_end + 1;

    // Skip Space
    if (cursor >= end || *cursor != ' ') return false;
    cursor++;

    // 2. Parse SEVERITY
    if (cursor >= end || *cursor != '[') return false;
    cursor++;
    token_start = cursor;
    token_end = memchr(cursor, ']', end - cursor);
    if (!token_end) return false;
    out_entry->severity = (log_slice_t){ .ptr = token_start, .len = (size_t)(token_end - token_start) };
    cursor = token_end + 1;

    // Skip Space
    if (cursor >= end || *cursor != ' ') return false;
    cursor++;

    // 3. Parse SERVICE
    if (cursor >= end || *cursor != '[') return false;
    cursor++;
    token_start = cursor;
    token_end = memchr(cursor, ']', end - cursor);
    if (!token_end) return false;
    out_entry->service = (log_slice_t){ .ptr = token_start, .len = (size_t)(token_end - token_start) };
    cursor = token_end + 1;

    // Skip Space
    if (cursor >= end || *cursor != ' ') return false;
    cursor++;

    // 4. Parse Remaining MESSAGE
    out_entry->message = (log_slice_t){ .ptr = cursor, .len = (size_t)(end - cursor) };

    return true;
}

int main(void) {
    char sample_log[] = "[2026-03-30T10:15:30.123Z] [ERROR] [auth-gateway] Connection timeout to database cluster 10.0.12.4";
    size_t log_len = strlen(sample_log);

    parsed_log_entry_t entry;
    if (parse_log_line(sample_log, log_len, &entry)) {
        printf("Parsed Log Successfully Without Allocations:\n");
        printf("Time     : %.*s\n", (int)entry.timestamp.len, entry.timestamp.ptr);
        printf("Severity : %.*s\n", (int)entry.severity.len, entry.severity.ptr);
        printf("Service  : %.*s\n", (int)entry.service.len, entry.service.ptr);
        printf("Message  : %.*s\n", (int)entry.message.len, entry.message.ptr);
    } else {
        fprintf(stderr, "Log line format parsing failed!\n");
        return 1;
    }
    return 0;
}
```

#### Langkah 2: Kompilasi dengan Strict Enterprise Instrumentation Flags
```bash
gcc -std=c11 -Wall -Wextra -Wpedantic -Werror \
    -O3 -g -fsanitize=address,undefined \
    -o zero_copy_log zero_copy_log.c
```

#### Langkah 3: Eksekusi dan Verifikasi Zero Memory Leaks
```bash
./zero_copy_log
```
*Output harus berhasil memetakan 4 field tanpa warning atau runtime crash dari AddressSanitizer.*

---

### 13. Exercises

#### Level Easy
Ubah implementasi `sv_slice` pada Bab 7.1 agar menghasilkan return error kode jika indeks `start` atau `end` melebihi panjang string view, alih-alih menggunakan terminasi `assert()`. Ujilah fungsi baru tersebut menggunakan test runner sederhana.

#### Level Medium
Buat struktur fungsi `sv_trim(string_view_t *sv)` yang membuang *whitespace* (`' '`, `'\t'`, `'\r'`, `'\n'`) dari awalan dan akhiran `string_view_t` langsung dengan memanipulasi pointer `data` dan integer `len` tanpa menyalin byte apa pun.

#### Level Hard
Rancang modul POSIX Vectorized I/O Wrapper. Buat fungsi:
```c
ssize_t send_framed_message(int socket_fd, const void *header, size_t header_len, const void *payload, size_t payload_len);
```
Fungsi tersebut harus menggunakan system call `writev` untuk mengirimkan frame paket dalam format: `[Header Length (4 bytes)][Header Content][Payload Length (4 bytes)][Payload Content]` ke dalam socket descriptor lewat satu atomic system call invocations tanpa melakukan buffer merge via `memcpy`.

---

### 14. Architecture Challenge
Rancang arsitektur buffer pipeline engine untuk **In-Memory Time Series Storage Engine** dengan spesifikasi berikut:
1. **Beban:** 10 Gbps inbound ingestion stream via TCP.
2. **Keterbatasan:** Alokasi heap (`malloc`/`calloc`) dilarang dipanggil setelah inisialisasi boot up selesai.
3. **Problem Masalah Lingkaran (Wraparound):** Circular Ring Buffer tradisional memiliki kelemahan: frame biner yang berukuran dinamis dapat terpotong di perbatasan akhir buffer array dan indeks awal (wrap-around edge boundary), memaksa fragmentasi atau salinan ekstra (*unsplit memory*).
4. **Tantangan:** Tuliskan proposal desain arsitektur menggunakan teknik **Virtual Memory Mirroring Technique** (memanfaatkan POSIX memory mapping ganda `mmap` dan `ftruncate`/`shm_open` yang menunjuk ke single contiguous physical page frame yang sama) untuk membuat ring buffer tanpa resiko wrap-around split boundary. Jelaskan bagaimana pointer window dapat membaca secara continuous melewati batas akhir tanpa menduplikasi data memory!

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Mengapa memanggil `strlen(char *str)` berulang kali di dalam kondisi perulangan `for (int i = 0; i < strlen(s); i++)` merupakan antipattern performa kritis?
   - *Jawaban:* `strlen` adalah operasi $\mathcal{O}(N)$ yang memindai memori sampai byte `\0`. Menempatkannya di kondisi loop mengubah kompleksitas algoritma traversal dari $\mathcal{O}(N)$ menjadi $\mathcal{O}(N^2)$.
2. Apa tujuan penggunaan compiler attribute/specifier `alignas(64)` pada struktur concurrent C?
   - *Jawaban:* Memaksa alignment struktur memori berada di kelipatan 64-byte (sesuai ukuran cache line arsitektur CPU modern), mencegah terjadinya False Sharing antar core cache.
3. Mengapa `string_view` tidak aman untuk langsung diumpankan ke parameter library C standar seperti `fopen()`?
   - *Jawaban:* `fopen` mewajibkan *null-terminated string*, sedangkan `string_view` tidak menjamin adanya byte `\0` pada akhir rentang memorinya, berpotensi memicu segment violation atau pembacaan path korup.
4. Apa perbedaan esensial dari memory order `memory_order_relaxed` dan `memory_order_release`?
   - *Jawaban:* `memory_order_relaxed` hanya menjamin atomisitas operasi tanpa ordering constraint, sedangkan `memory_order_release` bertindak sebagai memory barrier yang menjamin semua write operations sebelumnya terlihat oleh thread lain sebelum write operasi ini dipublikasikan.
5. Apa kelemahan utama fungsi standard POSIX `strtok()` dalam arsitektur multi-thread?
   - *Jawaban:* `strtok` menggunakan static global internal buffer state pointer, menjadikannya thread-unsafe (*non-reentrant*) dan merusak (memutasi) buffer string asli dengan memasukkan karakter `\0`.

#### 5 Pertanyaan Intermediate
6. Bagaimana cara compiler mendeteksi unaligned memory access jika CPU target tidak mendukung unaligned memory instruction?
   - *Jawaban:* Compiler akan mengeluarkan urutan instruksi byte-shift manual (misal: multi load byte dan shift OR), atau jika dipaksa direct dereference unaligned type pointer, kernel/CPU akan menembakkan exception trap fault `SIGBUS`.
7. Jelaskan bagaimana vector I/O `writev()` mengurangi overhead context switch dibandingkan pemanggilan ganda `write()` beruntun!
   - *Jawaban:* `writev` hanya membutuhkan satu kali transisi user-to-kernel mode (ring-3 ke ring-0 switch) untuk mengirim beberapa memory segment yang tidak bersambung (*non-contiguous chunks*), sedangkan serangkaian `write()` menuntut cost context switch per chunk.
8. Apa yang menyebabkan *TLB (Translation Lookaside Buffer) Thrashing* saat memproses array biner sangat besar?
   - *Jawaban:* Jika loop array mengakses memori dengan stride besar melewati boundary page standar (4KB), CPU kehabisan slot cache TLB untuk memetakan Virtual Address ke Physical Address, memicu berulang kali *Page Table Walks* lambat ke DRAM.
9. Mengapa pada circular queue ring buffer, kapasitas berukuran $2^N$ selalu dipilih dalam implementasi ultra-low latency?
   - *Jawaban:* Operasi pembagian integer modulo (`%`) pada hardware membutuhkan 10-40 cycle CPU ALU, sedangkan bitwise AND mask (`& (2^N - 1)`) hanya butuh 1 clock cycle.
10. Bagaimana macro `__builtin_prefetch()` membantu memproses contiguous array?
    - *Jawaban:* Menginstruksikan CPU pipeline secara asinkron untuk memuat memory line spesifik dari DRAM ke L1/L2 cache sebelum instruksi data dereference dijalankan, menyembunyikan memory latency overhead.

#### 3 Skenario Kasus Produksi
11. **Skenario 1:** Sebuah daemon service parsing URL gateway mengalami *segmentation fault crash* sporadis hanya saat sistem berada dalam kondisi load traffic puncak (>50,000 req/sec). AddressSanitizer menunjukkan jejak heap read out-of-bounds pada modul parser. Apa investigasi root cause Anda?
    - *Jawaban Analisis:* Kemungkinan besar parser mengandalkan token delimiter berbasis `\0`. Pada load tinggi, paket TCP tersegmentasi (TCP fragmentation) sehingga boundary terminator tidak terkirim lengkap dalam satu staging read buffer. Parser membaca melampaui buffer payload yang belum utuh. Solusinya adalah mengubah arsitektur parser menjadi streaming state machine eksplisit berbasis length offset `string_view` dan window slice boundary check.
12. **Skenario 2:** Profiler memori menunjukkan throughput sistem turun 70% ketika dua thread paralel dijalankan pada arsitektur dual-socket NUMA. Kedua thread tersebut menulis data counter ke indeks struct array global yang bersebelahan: `stats[0].count++` (Thread A) dan `stats[1].count++` (Thread B). Identifikasi masalah dan solusinya!
    - *Jawaban Analisis:* Masalah ini adalah **False Sharing**. `stats[0]` dan `stats[1]` berada dalam cache line 64-byte yang sama. Protokol MESI/MOESI memaksa cache line di-invalidasi bolak-balik antar socket L1/L2 cache (cache bouncing). Solusinya: beri padding struktural atau `alignas(64)` pada `stats_t` agar tiap counter menempati cache line independen.
13. **Skenario 3:** Tim pengembang mengimplementasikan `mmap(MAP_SHARED)` untuk memetakan file database biner 50GB. Namun saat proses membaca slice array secara random, latency per-transaksi melonjak hingga 15 milidetik. Apa penyebabnya dan bagaimana optimasinya?
    - *Jawaban Analisis:* Akses acak pada file 50GB memicu major synchronous Page Faults karena kernel harus membaca blok hard disk/SSD secara mendadak ke physical frame RAM. Optimasi: (1) Gunakan system call `madvise(addr, len, MADV_WILLNEED | MADV_RANDOM)` untuk memberi hint ke kernel I/O subsystem; (2) Aktifkan Linux Transparent Huge Pages (HugeTLB) untuk memperbesar ukuran page dari 4KB menjadi 2MB, mereduksi TLB miss rates.

---

### 16. Summary
- Pemrosesan buffer dan string berkinerja tinggi dalam C modern enterprise menuntut pergeseran dari paradigma salin-memori naif (*copy-heavy / null-terminated paradigm*) menuju **Zero-Copy Memory Slicing / String Views**.
- Pemahaman mendalam mengenai arsitektur perangkat keras—seperti struktur **64-byte Cache Line**, **Spatial Locality**, pencegahan **False Sharing**, serta perataan batas memori (**Memory Alignment**)—merupakan prasyarat fundamental untuk mengeliminasi bottleneck komputasi.
- Penggunaan struktur **SPSC Lock-Free Ring Buffer** dan POSIX **Scatter-Gather I/O (`iovec`)** memungkinkan throughput streaming jutaan transaksi per detik dengan latensi deterministik tanpa menghasilkan beban polusi heap ataupun system call context-switch overhead yang berlebihan.