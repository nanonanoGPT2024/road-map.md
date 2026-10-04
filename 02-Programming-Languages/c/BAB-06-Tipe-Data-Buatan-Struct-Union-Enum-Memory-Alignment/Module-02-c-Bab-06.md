# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 06: Tipe Data Buatan (Struct, Union, Enum, Memory Alignment)**  
**Kategori: 02-Programming-Languages / C**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis & Mengontrol Memory Alignment:** Menghitung padding, layout memori, dan mengendalikan alignment struct menggunakan standar C11 (`alignas`, `alignof`, `max_align_t`) serta atribut compiler (`__attribute__((packed))`, `#pragma pack`) untuk efisiensi transfer data dan cache CPU.
2. **Mencegah Kerusakan Data Akibat Strict Aliasing:** Mengimplementasikan teknik *type punning* yang aman dan conformant terhadap standar ISO C11 (Union vs `memcpy`) tanpa memicu *Undefined Behavior* (UB) akibat pelanggaran *Strict Aliasing Rule*.
3. **Mengoptimalkan Cache-Line & Menghilangkan False Sharing:** Mendesain struct untuk arsitektur multicore konkurensi tinggi dengan memisahkan state write-heavy menggunakan batasan cache line (64-byte padding).
4. **Mengimplementasikan Struktur Data Intrusif Tingkat Lanjut:** Membangun *Intrusive Linked List* dan *Polymorphism berbasis C* menggunakan makro `offsetof` dan `container_of` sesuai standar arsitektur kernel Linux.
5. **Membangun Sistem Serialization Zero-Copy:** Mengombinasikan *Flexible Array Member (FAM)*, *Tagged Union*, dan *Opaque Struct* untuk sistem transmisi protokol biner berkecepatan tinggi (*low latency*) yang siap produksi.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib memahami secara mendalam:
* Dasar-dasar pointer, aritmatika pointer, dan *void pointer* (`void*`).
* Representasi tipe data primitif dan komplemen dua pada level bit/byte (Endianness: Big-Endian vs Little-Endian).
* Alokasi memori dinamis dasar (`malloc`, `calloc`, `realloc`, `free`) dari `<stdlib.h>`.
* Modul 01: Sintaks dasar deklarasi `struct`, `union`, `enum`, dan `typedef`.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Hardware Memory Bus & Alignment Requirements
Arsitektur prosesor modern (x86_64, AArch64) tidak membaca memori byte-per-byte. Memori diakses melalui *memory bus* dalam ukuran kata (*word granularity*: 4-byte, 8-byte, hingga 64-byte per transfer burst).

```
Memori Fisik (Skema 64-bit Word Bus):
[Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7] -> 1 Siklus Bus
[Byte 8 | Byte 9 | Byte 10| Byte 11| Byte 12| Byte 13| Byte 14| Byte 15] -> 1 Siklus Bus
```

Jika data 4-byte (misalnya `uint32_t`) berada di alamat `0x0001` (*unaligned*):
1. CPU harus melakukan **dua kali memory read**: Bus cycle 1 membaca `0x0000 - 0x0007`, Bus cycle 2 membaca `0x0008 - 0x000F`.
2. Hardware harus melakukan *shifting* dan *masking* register untuk menyatukan potongan data tersebut.
3. Pada arsitektur x86_64, ini menghasilkan *latency penalty* (penalti siklus clock CPU). Pada beberapa mikroarsitektur ARMv7, SPARC, atau MIPS, tindakan ini memicu *hardware fault trap* langsung: `SIGBUS` (*Bus Error*).

**Aturan Alignment Alami (Natural Alignment):**  
Sebuah variabel berukuran $N$ byte harus dialokasikan pada alamat memori yang merupakan kelipatan dari $N$ (`address % N == 0`).
* `char` (1 byte): Alignment 1 (alamat bebas).
* `uint16_t` (2 byte): Alignment 2 (alamat genap).
* `uint32_t` (4 byte): Alignment 4 (kelipatan 4).
* `uint64_t` / `void*` (8 byte): Alignment 8 (kelipatan 8).

### 3.2 Struct Padding, Holes, dan Tail Padding
Kompiler menyisipkan byte kosong tak terlihat (*padding bytes*) di antara anggota struct untuk memastikan *natural alignment* setiap field terpenuhi, serta menyisipkan *tail padding* agar ukuran total struct merupakan kelipatan dari alignment terbesar field di dalamnya.

Perhatikan perbandingan berikut:

```c
// BURUK: Boros Memori (24 Bytes)
struct Unoptimized {
    char   a;      // 1 byte
    // 7 bytes padding di sini
    double b;      // 8 bytes (harus kelipatan 8)
    int    c;      // 4 bytes
    // 4 bytes tail padding di sini (agar total kelipatan 8)
}; // Total: 24 bytes

// OPTIMAL: Hemat Memori (16 Bytes)
struct Optimized {
    double b;      // 8 bytes (offset 0)
    int    c;      // 4 bytes (offset 8)
    char   a;      // 1 byte  (offset 12)
    // 3 bytes tail padding di sini (agar total kelipatan 8)
}; // Total: 16 bytes
```

### 3.3 Cache Lines, False Sharing, dan Cache Alignment
Prosesor modern memiliki Cache L1/L2/L3 yang terorganisir dalam satuan *Cache Line* (umumnya berukuran 64 bytes). 
Jika dua thread berbeda pada dua core terpisah memodifikasi dua variabel berbeda yang kebetulan berada di dalam **satu cache line yang sama**, arsitektur *Cache Coherency Hardware* (protokol MESI/MOESI) akan saling menganulir (invalidate) cache line tersebut bolak-balik antar core. Fenomena ini disebut **False Sharing**, yang merusak skalabilitas performa multithreading secara drastis.

Solusi enterprise: Menggunakan `alignas(64)` dari standar C11 `<stdalign.h>` untuk memisahkan field write-heavy ke dalam cache line terisolasi.

### 3.4 Strict Aliasing Rule & Type Punning (C11 §6.5/7)
Kompiler modern berasumsi bahwa dua pointer dari tipe dasar yang berbeda tidak akan menunjuk ke lokasi memori yang sama (kecuali `char*`, `signed char*`, atau `unsigned char*`). Ini memungkinkan compiler melakukan optimasi register reordering secara agresif.

```c
// ILEGAL / UNDEFINED BEHAVIOR: Pelanggaran Strict Aliasing
float f = 5.25f;
int32_t *p = (int32_t *)&f; // UB! Akses nilai float via int32_t*
printf("%08x\n", *p);

// LEGAL (C11): Type Punning via Union
union {
    float f;
    int32_t i;
} punner;
punner.f = 5.25f;
int32_t val = punner.i; // Valid di C99/C11 (Annex J.5.7)

// LEGAL (Universal & Idiomatic): memcpy
int32_t val2;
memcpy(&val2, &f, sizeof(val2)); // Dioptimasi compiler jadi 0-cost mov register
```

---

## 4. Why & What

| Dimensi | Mengapa Dibutuhkan di Arsitektur Enterprise? | Apa Dampak Jika Salah Diterapkan? |
| :--- | :--- | :--- |
| **Manual Alignment & Packing** | Dibutuhkan saat mendefinisikan layout protokol jaringan (IP, TCP) atau format biner disk yang wajib strictly packed byte-per-byte tanpa compiler padding. | Unaligned memory access fault (`SIGBUS`), korupsi offset data, atau performa I/O anjlok drastis. |
| **Cache Line Padding** | Menjamin lock-free ring buffer dan per-thread state tidak mengalami degradasi performa pada sistem multicore. | *False sharing*: performa throughput multithread drop hingga 80-95% dibanding single-thread. |
| **Flexible Array Member (FAM)** | Mengalokasikan struct metadata dan buffer payload dalam satu kali pemanggilan `malloc` contiguous memory chunk. | Fragmentation memory heap, cache misses berlebihan akibat multi-pointer chasing (`struct->ptr->data`). |
| **Intrusive Structures** | Memungkinkan satu objek dimasukkan ke dalam banyak list sekaligus tanpa alokasi memori tambahan per-node (pola Kernel Linux). | Alokasi berulang per-node (`malloc(sizeof(Node))`) yang menyebabkan memory fragmentation dan pointer indirection latency. |

---

## 5. How (Workflow Detail)

Berikut alur perancangan memori untuk struct siap produksi berkecepatan tinggi:

```
[Mulai Desain Tipe Data]
          │
          ▼
Urutkan Field Berdasarkan Ukuran (Descending: 64b -> 32b -> 16b -> 8b)
          │
          ▼
Apakah Struct Digunakan Antar Thread Berbeda (Multithread Write)?
   ├─► YA: Sisipkan alignas(64) pada boundary field atau tail padding 64 byte.
   └─► TIDAK: Lanjut.
          │
          ▼
Apakah Struct adalah Frame Jaringan / Protokol Biner Hardisk?
   ├─► YA: Gunakan `#pragma pack(push, 1)` atau `__attribute__((packed))`.
   │       Waspadai: JANGAN dereferensi pointer field unaligned! Salin via memcpy.
   └─► TIDAK: Lanjut.
          │
          ▼
Apakah Payload Memiliki Ukuran Dinamis?
   ├─► YA: Gunakan Flexible Array Member (FAM) di akhir struct: `uint8_t payload[];`
   └─► TIDAK: Lanjut.
          │
          ▼
Verifikasi Otomatis Ukuran & Alignment saat Kompilasi:
   Gunakan `static_assert(sizeof(...) == TARGET, "Layout Error!");`
          │
          ▼
[Selesai - Siap Produksi]
```

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi Kontainer Kargo vs Rak Lemari
Bayangkan memori sebagai rak dengan kompartemen berlebar 8 slot (8-byte word alignment). 
* **Unaligned Struct:** Memasukkan kardus berukuran 4-slot sembarangan. Satu kardus melintang dari slot 7 di rak pertama hingga slot 2 di rak kedua. Saat kurir (CPU) ingin mengambil kardus tersebut, dia harus membuka **dua pintu rak**, memotong selotip di tengah, lalu merekatkannya kembali.
* **Aligned Struct:** Kardus 4-slot diletakkan tepat di slot 0 atau slot 4. Kurir cukup membuka **satu pintu rak** dan mengambilnya dalam satu gerakan instan.

### 6.2 Diagram Memori: Struct Padding vs Cache Line

```
=== UNPACKED STRUCT DENGAN PADDING (Alignment Alami) ===
Byte: 00 01 02 03 04 05 06 07 | 08 09 10 11 12 13 14 15 | 16 17 18 19 20 21 22 23
Data: [a ] [  PAD 7-BYTES   ] | [       double b        ] | [   int c   ] [ PAD 4 ]
      ^                       | ^                         | ^
      offset 0                | offset 8                  | offset 16

=== INTRUSIVE LINKED LIST CONTAINER MAPPING ===
Alamat Memori Objek Induk (struct Device):
+------------------------------------+ <--- [Alamat Asal Objek: 0x1000]
| char name[16];                     |
+------------------------------------+
| struct list_head node;             | <--- [Pointer Aktif: 0x1010 (offset: 16)]
|   - struct list_head *next;        |
|   - struct list_head *prev;        |
+------------------------------------+
| int device_id;                     |
+------------------------------------+
Operasi container_of(ptr, struct Device, node):
0x1010 - offsetof(struct Device, node) [16] = 0x1000 (Mengembalikan struct Device*)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Static Alignment Assertion & Padding Analysis
Kode ini mendemonstrasikan penghitungan padding, inspeksi offset menggunakan `<stddef.h>`, dan proteksi layout menggunakan C11 `<assert.h>` via `static_assert`.

```c
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <assert.h>
#include <stdalign.h>

struct MemoryAudit {
    uint8_t  flag;       // 1 byte
    // Compiler menyisipkan 3 bytes padding di sini
    uint32_t counter;    // 4 bytes
    uint16_t mask;       // 2 bytes
    // Compiler menyisipkan 6 bytes padding di sini
    uint64_t timestamp;  // 8 bytes
};

// Verifikasi compile-time: ukuran struct harus 24 byte, bukan 1+4+2+8 = 15 byte
static_assert(sizeof(struct MemoryAudit) == 24, "Unexpected struct padding layout!");
static_assert(alignof(struct MemoryAudit) == 8, "Struct alignment must be 8-byte boundary!");

int main(void) {
    printf("=== STRUCT MEMORY AUDIT ===\n");
    printf("Total Size: %zu bytes\n", sizeof(struct MemoryAudit));
    printf("Alignment : %zu bytes\n", alignof(struct MemoryAudit));
    printf("Offset flag     : %zu\n", offsetof(struct MemoryAudit, flag));
    printf("Offset counter  : %zu\n", offsetof(struct MemoryAudit, counter));
    printf("Offset mask     : %zu\n", offsetof(struct MemoryAudit, mask));
    printf("Offset timestamp: %zu\n", offsetof(struct MemoryAudit, timestamp));
    return 0;
}
```

### 7.2 Practical Example: Zero-Copy Network Packet Framing (FAM + Packed Struct)
Contoh standar industri telekomunikasi: Menguraikan frame jaringan menggunakan kombinasi *Packed Struct* untuk header biner dan *Flexible Array Member (FAM)* untuk buffer payload nol alokasi pointer ganda.

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>

#pragma pack(push, 1)
// Header jaringan 1-byte aligned tanpa compiler padding
typedef struct {
    uint16_t magic;      // 0xAA55
    uint8_t  msg_type;   // 0x01 = DATA, 0x02 = HEARTBEAT
    uint32_t payload_len;// Panjang payload aktual
} PacketHeader;
#pragma pack(pop)

// Paket lengkap dengan Flexible Array Member (FAM)
typedef struct {
    PacketHeader header;
    uint8_t      payload[]; // FAM: Ukuran dinamis, tidak menambah sizeof(PacketFrame)
} PacketFrame;

static_assert(sizeof(PacketHeader) == 7, "PacketHeader must be strictly 7 bytes packed!");
static_assert(sizeof(PacketFrame) == 7, "PacketFrame base size must equal PacketHeader!");

PacketFrame* packet_create(uint8_t msg_type, const void* data, uint32_t length) {
    // Alokasi memori tunggal yang contiguous: Header + Payload
    PacketFrame *pkt = (PacketFrame *)malloc(sizeof(PacketFrame) + length);
    if (!pkt) {
        return NULL;
    }

    pkt->header.magic = 0xAA55;
    pkt->header.msg_type = msg_type;
    pkt->header.payload_len = length;

    if (data && length > 0) {
        memcpy(pkt->payload, data, length);
    }

    return pkt;
}

void packet_process(const PacketFrame *pkt) {
    printf("Packet Received! Type: 0x%02X, Size: %u bytes\n", 
           pkt->header.msg_type, pkt->header.payload_len);
    
    // Akses payload secara langsung via contiguous buffer
    printf("Payload Raw Hex: ");
    for (uint32_t i = 0; i < pkt->header.payload_len; ++i) {
        printf("%02X ", pkt->payload[i]);
    }
    printf("\n");
}

int main(void) {
    const char *telemetry = "ENGINE_OK_TEMP_85C";
    uint32_t len = (uint32_t)strlen(telemetry);

    PacketFrame *pkt = packet_create(0x01, telemetry, len);
    if (!pkt) {
        perror("Failed to allocate packet");
        return 1;
    }

    packet_process(pkt);

    free(pkt);
    return 0;
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Ultra-Low-Latency Order Router (High-Frequency Trading)
Pada sistem perdagangan bursa berkecepatan tinggi, latensi diukur dalam fraksi *sub-microsecond*. Dua masalah utama diidentifikasi pada sistem lama:
1. **False Sharing:** Variabel `metrics_rx_count` (diupdate Core 1) dan `metrics_tx_count` (diupdate Core 2) berada dalam satu struct ringkas, memicu pembatalan cache line berulang kali dan meningkatkan latensi 99th-percentile hingga 600ns.
2. **Pola Parsing Berbasis Heap:** Setiap pesan *Order* dialokasikan melalui `malloc` dengan pointer ke sub-struct payload.

### Solusi Arsitektur
1. Menggunakan **Tagged Union** dengan discriminator eksplisit untuk memproses ragam pesan transaksi dalam buffer tetap (in-place zero allocation).
2. Memisahkan cache line data thread antar-core menggunakan `alignas(64)`.
3. Membangun implementasi struktur data intrusif untuk mendistribusikan antrean tanpa *per-node heap overhead*.

```c
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <stdalign.h>
#include <assert.h>

// Definisi Pola Linux Kernel Intrusive Node
struct list_node {
    struct list_node *next;
    struct list_node *prev;
};

#define container_of(ptr, type, member) \
    ((type *)((char *)(ptr) - offsetof(type, member)))

// Enum Discriminator untuk Tagged Union
typedef enum {
    ORDER_TYPE_NEW    = 1,
    ORDER_TYPE_CANCEL = 2,
    ORDER_TYPE_MODIFY = 3
} OrderType;

// Payload Structs
typedef struct {
    uint64_t order_id;
    uint32_t price_cents;
    uint32_t quantity;
    char     symbol[8];
} OrderNew;

typedef struct {
    uint64_t order_id;
    uint64_t client_timestamp;
} OrderCancel;

// Tagged Union Order Event
typedef struct {
    OrderType type;
    union {
        OrderNew    new_order;
        OrderCancel cancel_order;
    } as;
} OrderEvent;

// Objek Lengkap dengan Node Intrusif
typedef struct {
    struct list_node node; // Tersemat langsung dalam objek
    OrderEvent       event;
} OrderContainer;

// State Konkurensi: Menghindari False Sharing antar Thread Core
struct OrderBookCoreContext {
    // Diproses eksklusif oleh Core 1 (Ingress Thread)
    alignas(64) uint64_t ingress_sequence;
    uint64_t rx_packet_count;

    // Diproses eksklusif oleh Core 2 (Matching Engine Thread)
    alignas(64) uint64_t matched_orders_count;
    uint64_t execution_volume;
};

static_assert(offsetof(struct OrderBookCoreContext, matched_orders_count) >= 64, 
              "Critical: False sharing boundary violation!");

void execute_order(struct list_node *node) {
    // Resolusi pointer balik dari intrusive node ke OrderContainer
    OrderContainer *order = container_of(node, OrderContainer, node);

    switch (order->event.type) {
        case ORDER_TYPE_NEW:
            printf("[MATCHING ENGINE] New Order: ID %lu, Sym: %s, Price: $%u.%02u, Qty: %u\n",
                   order->event.as.new_order.order_id,
                   order->event.as.new_order.symbol,
                   order->event.as.new_order.price_cents / 100,
                   order->event.as.new_order.price_cents % 100,
                   order->event.as.new_order.quantity);
            break;
        case ORDER_TYPE_CANCEL:
            printf("[MATCHING ENGINE] Cancel Order: ID %lu\n",
                   order->event.as.cancel_order.order_id);
            break;
    }
}

int main(void) {
    OrderContainer live_order;
    live_order.event.type = ORDER_TYPE_NEW;
    live_order.event.as.new_order.order_id = 90214012;
    live_order.event.as.new_order.price_cents = 45050; // $450.50
    live_order.event.as.new_order.quantity = 150;
    snprintf(live_order.event.as.new_order.symbol, 8, "BBCA");

    // Simulasi node ditautkan ke linked list
    struct list_node *raw_list_head = &live_order.node;

    // Matching engine hanya menerima struct list_node* tanpa tau tipe konkret
    execute_order(raw_list_head);

    return 0;
}
```

---

## 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Biaya & Kompensasi (Trade-offs) |
| :--- | :--- | :--- |
| **`__attribute__((packed))`** | Ukuran memory footprint minimal, wire-compatibility langsung tanpa gap bit biner. | Eksekusi baca/tulis CPU lebih lambat karena unaligned access. Menyebabkan hardware abort pada arsitektur RISC tertentu jika dieksploitasi sembarangan. |
| **Cache Padding (`alignas(64)`)** | Menghilangkan *False Sharing* sepenuhnya; mendongkrak performa multithreaded skala besar. | Terjadinya *internal memory bloat/waste* (pemborosan memori akibat padding kosong hingga puluhan byte per instans). |
| **Intrusive Data Structures** | *Zero-allocation* untuk penambahan node; cache locality sangat tinggi; sebuah struct dapat berada di banyak container bersamaan. | API lebih kompleks; mengorbankan enkapsulasi tipe; dereferensi manual via pointer math (`container_of`). |
| **Opaque Pointer (PIMPL in C)** | Enkapsulasi sempurna (header file hanya memuat `typedef struct Engine Engine;`). ABI stabil. | Alokasi heap wajib per instans; indirection pointer hop menambah latency (mengurangi cache locality). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Pelanggaran Dereferensi Pointer Unaligned
```c
// KODE BERBAHAYA
#pragma pack(push, 1)
struct NetPayload {
    uint8_t  flag;
    uint32_t val; // Offset 1 (Tidak kelipatan 4!)
};
#pragma pack(pop)

void process(struct NetPayload *payload) {
    // RISIKO TINGGI: Menunjuk pointer uint32_t* ke alamat unaligned
    uint32_t *ptr = &payload->val;
    // Pada CPU ARM: Memori trap (SIGBUS) atau korupsi silent data
    printf("%u\n", *ptr); 
}

// SOLUSI AMAN: Salin byte menggunakan memcpy
void process_safe(struct NetPayload *payload) {
    uint32_t val;
    memcpy(&val, &payload->val, sizeof(val));
    printf("%u\n", val);
}
```

### 10.2 Salah Mengukur Alokasi Flexible Array Member (FAM)
```c
// KODE SALAH
typedef struct {
    uint32_t size;
    uint8_t  data[];
} Buffer;

// FATAL: sizeof(Buffer*) hanya mengalokasikan ukuran POINTER (8 bytes), bukan struct!
Buffer *b = (Buffer *)malloc(sizeof(Buffer*) + 100); 

// FATAL: sizeof(Buffer) benar, namun salah menghitung total kapasitas buffer
Buffer *b2 = (Buffer *)malloc(sizeof(Buffer)); // data[] memiliki ukuran 0 bytes, buffer overflow saat ditulis!

// SOLUSI BENAR
Buffer *b_ok = (Buffer *)malloc(sizeof(Buffer) + (sizeof(uint8_t) * 100));
b_ok->size = 100;
```

---

## 11. Best Practices (Production Checklist)

* [ ] Urutkan susunan deklarasi field struct dari ukuran tipe data terbesar ke terkecil (*descending*) untuk meminimalisasi *compiler padding waste*.
* [ ] Lindungi ABI struct tetap stabil di level kompilasi menggunakan `static_assert(sizeof(...) == N, "ABI Breakage")`.
* [ ] Selalu isolasi variabel atomik / write-heavy antar worker thread yang berbeda ke dalam boundary cache terpisah menggunakan `alignas(64)`.
* [ ] Terapkan penulisan protokol transmisi biner dengan *Network Byte Order* conversion (`htons`, `ntohs`, `htonl`, `ntohl`) saat mapping ke struct packed.
* [ ] Larang keras casting pointer berbeda tipe untuk *type punning*; gunakan `union` standar atau `memcpy`.
* [ ] Jalankan pipeline pengujian dengan flag kompilasi: `-Wall -Wextra -Werror -Wpadded -Wcast-align -fsanitize=address,undefined`.

---

## 12. Hands-on Practice

Target pengerjaan: Simpan seluruh artefak ke direktori `hands-on/m02/`.

### 12.1 Struktur Direktori
```
hands-on/m02/
├── Makefile
├── protocol.h
├── protocol.c
└── main.c
```

### 12.2 `hands-on/m02/protocol.h`
```c
#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>
#include <stddef.h>
#include <stdalign.h>

#define MAX_PAYLOAD_SIZE 1024

typedef enum {
    CMD_PING   = 0x01,
    CMD_METRIC = 0x02,
    CMD_LOG    = 0x03
} CommandType;

#pragma pack(push, 1)
typedef struct {
    uint16_t sync_word;
    uint8_t  command;
    uint16_t payload_len;
} WireHeader;
#pragma pack(pop)

typedef struct {
    WireHeader header;
    uint8_t    payload[];
} WireFrame;

// Ring buffer node yang diproteksi dari false sharing
typedef struct {
    alignas(64) uint64_t sequence;
    uint8_t  occupied;
    uint8_t  buffer[MAX_PAYLOAD_SIZE];
} CacheAlignedSlot;

WireFrame* wire_frame_create(CommandType cmd, const void *payload, uint16_t len);
void       wire_frame_destroy(WireFrame *frame);
int        wire_frame_serialize(const WireFrame *frame, uint8_t *out_stream, size_t max_out);

#endif // PROTOCOL_H
```

### 12.3 `hands-on/m02/protocol.c`
```c
#include "protocol.h"
#include <stdlib.h>
#include <string.h>

WireFrame* wire_frame_create(CommandType cmd, const void *payload, uint16_t len) {
    if (len > MAX_PAYLOAD_SIZE) return NULL;

    WireFrame *frame = (WireFrame *)malloc(sizeof(WireFrame) + len);
    if (!frame) return NULL;

    frame->header.sync_word = 0x55AA;
    frame->header.command = (uint8_t)cmd;
    frame->header.payload_len = len;

    if (payload && len > 0) {
        memcpy(frame->payload, payload, len);
    }

    return frame;
}

void wire_frame_destroy(WireFrame *frame) {
    free(frame);
}

int wire_frame_serialize(const WireFrame *frame, uint8_t *out_stream, size_t max_out) {
    if (!frame || !out_stream) return -1;

    size_t total_size = sizeof(WireHeader) + frame->header.payload_len;
    if (total_size > max_out) return -2;

    memcpy(out_stream, &frame->header, sizeof(WireHeader));
    if (frame->header.payload_len > 0) {
        memcpy(out_stream + sizeof(WireHeader), frame->payload, frame->header.payload_len);
    }

    return (int)total_size;
}
```

### 12.4 `hands-on/m02/main.c`
```c
#include "protocol.h"
#include <stdio.h>
#include <assert.h>

int main(void) {
    printf("=== ENTERPRISE PROTOCOL FRAMING ENGINE ===\n");

    const char *telemetry_msg = "HEALTH_STATUS=STABLE;TPS=45000";
    uint16_t msg_len = (uint16_t)strlen(telemetry_msg);

    WireFrame *tx_frame = wire_frame_create(CMD_METRIC, telemetry_msg, msg_len);
    assert(tx_frame != NULL);

    uint8_t wire_bytes[2048];
    int serialized_bytes = wire_frame_serialize(tx_frame, wire_bytes, sizeof(wire_bytes));
    assert(serialized_bytes > 0);

    printf("Serialized stream size: %d bytes (WireHeader: %zu, Payload: %u)\n",
           serialized_bytes, sizeof(WireHeader), tx_frame->header.payload_len);

    printf("Stream Verification: ");
    for (int i = 0; i < serialized_bytes; ++i) {
        printf("%02X ", wire_bytes[i]);
    }
    printf("\n");

    wire_frame_destroy(tx_frame);
    printf("Pipeline completed successfully.\n");
    return 0;
}
```

### 12.5 `hands-on/m02/Makefile`
```makefile
CC = gcc
CFLAGS = -Wall -Wextra -Werror -Wpadded -std=c11 -O2 -g
TARGET = protocol_engine

SRCS = protocol.c main.c
OBJS = $(SRCS:.c=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $(OBJS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: all clean
```

---

## 13. Exercise

### Level Easy
Terdapat deklarasi struct berikut:
```c
struct SensorData {
    char     sensor_id;
    uint64_t timestamp;
    uint16_t raw_reading;
    uint32_t calibration_factor;
};
```
* **Instruksi:** Tulis ulang deklarasi struct di atas tanpa mengubah tipe field sehingga penggunaan memori terminimalisasi secara optimal pada arsitektur 64-bit. Buktikan penghematan byte menggunakan `sizeof()`.

### Level Medium
Buatlah implementasi makro `my_offsetof(type, member)` dan program verifikasi untuk membuktikan makro tersebut menghasilkan output identik dengan makro standar `<stddef.h>` untuk berbagai jenis struct kompleks, termasuk nested struct.

### Level Hard
Implementasikan sebuah Generic Double Linked List Intrusif (`intrusive_list`) lengkap dengan fungsi:
* `list_init(struct list_node *head)`
* `list_add_tail(struct list_node *new_node, struct list_node *head)`
* Iterasi macro `list_for_each_entry(pos, head, member)`
Uji linked list ini untuk mengelola struct bertipe `WorkerTask` yang berisi metadata task ID, runtime priority, dan state mesin.

---

## 14. Challenge

### Studi Kasus: In-Memory Lock-Free Circular Ring Buffer IPC Engine
Rancang bangun sistem IPC (*Inter-Process Communication*) berbasis *Shared Memory* biner untuk dua proses independen (1 Producer, 1 Consumer).

**Kebutuhan Teknis:**
1. Desain struct `SharedRingBuffer` yang dipetakan pada contiguous memory chunk.
2. Head index dan Tail index wajib diisolasi dengan *cache alignment* (`alignas(64)`) agar Producer dan Consumer tidak saling memicu *False Sharing* saat memodifikasi pointer transaksi.
3. Gunakan *Tagged Union* sebagai format elemen pesan untuk mendukung transmisi 3 event yang berbeda ukuran (`HeartbeatEvent`, `TransactionEvent`, `AlertNotificationEvent`).
4. Pastikan struct aman terhadap *Undefined Behavior* dari *Strict Aliasing* dan sediakan verifikasi `static_assert` komprehensif atas boundary memory alignment.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. Berapa ukuran byte `sizeof(struct Demo)` jika berisi field: `char a; int b;` pada sistem x86_64 standar? Jelaskan mekanismenya!
2. Apa tujuan utama dari keyword `alignof` yang diperkenalkan pada standar C11?
3. Mengapa *Flexible Array Member* (FAM) wajib dideklarasikan sebagai elemen terakhir di dalam struct?
4. Mengapa kita tidak boleh menggunakan operator equality `==` secara langsung pada dua variabel struct (`if (struct_a == struct_b)`)?
5. Apa perbedaan mendasar antara alokasi memori `struct` vs `union`?

### Bagian 2: Intermediate (5 Soal)
6. Apa bahaya laten dereferensi langsung terhadap pointer yang dihasilkan dari atribut packing compiler: `__attribute__((packed))`?
7. Jelaskan bagaimana makro `container_of` di kernel Linux dapat mengembalikan alamat pointer struct induk hanya dari sebuah pointer field anggotanya!
8. Apa yang dimaksud dengan *Strict Aliasing Rule* dalam C, dan mengapa casting `int *pi = (int *)&my_float;` memicu *Undefined Behavior*?
9. Bagaimana cara kerja mekanisme *Tail Padding* pada sebuah struct yang berada di dalam array?
10. Mengapa `memcpy` sering kali menjadi pilihan terbaik untuk *Type Punning* pada kompiler C modern yang menerapkan optimasi tinggi (`-O3`)?

### Bagian 3: Skenario Kasus Produksi (3 Soal)

#### Skenario 1
Sebuah gateway telemetri IoT menerima stream biner dari sensor embedded melalui protokol serial. Data langsung di-cast ke pointer struct:
`SensorPacket *pkt = (SensorPacket *)rx_buffer;`
Aplikasi bekerja normal pada PC pengembang (arsitektur x86_64), namun mengalami crash mendadak akibat sinyal `SIGBUS` saat di-deploy ke unit produksi berbasis mikroprosesor ARM Cortex-M.  
*Pertanyaan:* Analisis akar penyebab (*root cause*) dan berikan perbaikan strukturalnya!

#### Skenario 2
Dua worker thread pada aplikasi database in-memory mencatat throughput yang anjlok secara drastis ketika dijalankan pada server 64-core, meskipun tidak ada locking (`mutex`) yang digunakan antar thread:
```c
struct CoreStats {
    uint64_t worker1_ops;
    uint64_t worker2_ops;
} g_stats;
```
Worker 1 terus mengeksekusi `g_stats.worker1_ops++` dan Worker 2 mengeksekusi `g_stats.worker2_ops++`.  
*Pertanyaan:* Masalah internal CPU apa yang terjadi di balik penurunan performa ini, dan bagaimana solusi C11 untuk mengatasinya?

#### Skenario 3
Seorang software engineer membuat struct untuk pengiriman frame via TCP:
```c
struct Packet {
    uint32_t length;
    char data[];
};
```
Ia menulis kode inisialisasi:
```c
struct Packet *p = malloc(sizeof(struct Packet));
p->length = 50;
memset(p->data, 0, 50);
```
Saat pengujian regresi beban tinggi, program mengalami *Heap Corruption Crash*.  
*Pertanyaan:* Tunjukkan kesalahan fatal pada alokasi tersebut dan tuliskan instruksi perbaikan kodenya!

---

### Kunci Jawaban & Evaluasi

#### Kunci Jawaban Basic
1. Ukurannya adalah **8 bytes**. `char a` menempati byte 0. `int b` memerlukan 4-byte natural alignment sehingga compiler menyisipkan padding 3 bytes (byte 1-3). Field `b` berada di byte 4-7.
2. `alignof` digunakan untuk mengueri persyaratan alignment (dalam byte) dari suatu tipe data pada arsitektur target saat waktu kompilasi.
3. Karena FAM tidak memiliki ukuran tetap (*offset* alamat tak terhingga). Jika ada field setelah FAM, compiler tidak dapat menentukan lokasi *offset* memori field tersebut.
4. Karena padding bytes di dalam struct berisi nilai tak terdefinisi (*indeterminate memory debris*). Membandingkan bit memori secara keseluruhan (`memcmp`) dapat menghasilkan *false negative*.
5. `struct` mengalokasikan ruang memori yang cukup untuk menyimpan **seluruh** anggotanya secara berdampingan. `union` mengalokasikan ruang memori hanya sebesar **anggota terbesarnya**, di mana seluruh anggotanya berbagi alamat memori awal yang sama.

#### Kunci Jawaban Intermediate
6. Pointer unaligned dapat memicu *Hardware Alignment Fault* (`SIGBUS`) pada arsitektur prosesor tertentu (seperti RISC/ARM), atau menyebabkan *split lock/multi-cycle access latency* parah pada arsitektur x86.
7. Dengan menghitung selisih offset byte dari field terhadap awal struct menggunakan makro `offsetof(type, member)`. Alamat pointer field saat ini dikurangi offset tersebut menghasilkan alamat basis dari struct pembungkusnya.
8. Standar C menyatakan pointer dari dua tipe yang berbeda tidak boleh menunjuk ke objek yang sama. Kompiler berasumsi pembacaan melalui pointer `int*` tidak dipengaruhi oleh modifikasi pada `float*`, sehingga compiler berhak melakukan reordering atau mengabaikan operasi baca/tulis yang memicu inkonsistensi data runtime.
9. *Tail padding* memastikan ketika struct tersebut disusun ke dalam sebuah array, elemen kedua, ketiga, dan seterusnya tetap berada pada batas *natural alignment* yang valid.
10. Kompiler modern mengenali pola `memcpy` untuk ukuran kecil/tetap dan langsung mentranslasikannya menjadi instruksi register CPU (`mov`) tanpa pemanggilan fungsi overhead, menjadikannya 0-cost, aman dari *strict aliasing*, dan sepenuhnya portable.

#### Kunci Jawaban Skenario Kasus Produksi
* **Skenario 1 (Root Cause & Solusi):**  
  *Root Cause:* Buffer serial `rx_buffer` tidak dialokasikan pada alamat kelipatan alignment field struct `SensorPacket` (misal kelipatan 4 atau 8). Arsitektur ARM secara default mengaktifkan *Alignment Fault Checking* yang membangkitkan `SIGBUS` saat membaca memory address yang unaligned.  
  *Solusi:* Hindari *typecasting* pointer buffer langsung. Gunakan `memcpy` untuk menduplikasi byte dari `rx_buffer` ke instans lokal `SensorPacket` yang telah ter-align secara valid oleh compiler.
* **Skenario 2 (Root Cause & Solusi):**  
  *Root Cause:* **False Sharing**. `worker1_ops` dan `worker2_ops` berada dalam satu cache line 64-byte yang sama. Ketika Core 1 menulis ke `worker1_ops`, cache L1 pada Core 2 dibatalkan (invalidated) via cache coherence bus, memicu *cache thrashing*.  
  *Solusi:* Pisahkan variabel ke dalam cache line terpisah menggunakan C11 `<stdalign.h>`:
  ```c
  struct CoreStats {
      alignas(64) uint64_t worker1_ops;
      alignas(64) uint64_t worker2_ops;
  } g_stats;
  ```
* **Skenario 3 (Root Cause & Solusi):**  
  *Root Cause:* `sizeof(struct Packet)` hanya menghitung ukuran base struct (yaitu `sizeof(uint32_t) = 4 bytes` plus tail padding jika ada). `malloc` hanya mengalokasikan ruang untuk metadata tanpa payload. Penulisan `memset(p->data, 0, 50)` menulis 50 bytes ke heap unallocated, merusak internal heap chunk metadata allocator.  
  *Solusi:* Alokasikan ukuran base struct ditambah ukuran payload dinamisnya:
  ```c
  struct Packet *p = malloc(sizeof(struct Packet) + (50 * sizeof(char)));
  p->length = 50;
  memset(p->data, 0, 50);
  ```

---

## 16. Summary

1. **Alignment & Hardware:** Kompiler C menyisipkan *internal padding* dan *tail padding* agar data berada pada batas *natural alignment* yang sesuai dengan arsitektur memory bus CPU.
2. **Cache Coherency:** Pada arsitektur multicore konkurensi tinggi, letak data dalam memori harus memperhatikan batas 64-byte *Cache Line* (`alignas(64)`) untuk mengeliminasi degradasi performa akibat *False Sharing*.
3. **Type Safety & Aliasing:** Standar C melarang type punning sembarangan via pointer casting (*Strict Aliasing Rule*). Penggunaan `union` terverifikasi atau fungsi `memcpy` adalah metode legal yang optimal.
4. **Desain Data Tingkat Lanjut:** Penerapan pola *Flexible Array Member (FAM)* memotong overhead *heap fragmentation*, sementara *Intrusive Structures* mengabstraksi pemrosesan linked list berkecepatan tinggi tanpa beban alokasi memori tambahan per node.