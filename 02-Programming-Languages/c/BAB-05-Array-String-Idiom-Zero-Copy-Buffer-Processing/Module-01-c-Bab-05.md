# SEKSI 01 — IDENTITAS MODUL

*   **Modul ID**: `C-02-05-01`
*   **Kategori**: `02-Programming-Languages`
*   **Jalur Kurikulum**: C Systems Programming
*   **Bab**: 05 — Data Structures, Memory Patterns, & High-Performance Buffers
*   **Topik**: Array, String Idiom, & Zero-Copy Buffer Processing
*   **Level**: Intermediate to Advanced
*   **Prasyarat**: Pemahaman mendalam tentang Pointer Basics (`*`, `&`), Stack vs Heap Allocation, Hexadecimal Memory Addressing, serta Alur Eksekusi C Standar (C99/C11).
*   **Tech Stack**: C99/C11, GCC/Clang, POSIX API, GDB, AddressSanitizer (ASan).
*   **Estimasi Waktu**: 6–8 Jam (Teori, Bedah Kode, Praktik Mandiri).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mendekonstruksi** fenomena *Array Decay* ke tingkat bahasa rakitan (assembly) dan menjelaskan perbedaan fundamental antara tipe array `T[N]` dan pointer `T*`.
2.  **Mengimplementasikan** idiom pemrosesan string C klasik dan modern berbasis pointer arithmetic berkinerja tinggi tanpa menimbulkan kerentanan buffer overflow atau *off-by-one*.
3.  **Merancang dan Menerapkan** paradigma *Zero-Copy Buffer Processing* menggunakan struktur data *String View / Slice* (`{const char *data; size_t len;}`) untuk mengeliminasi pemanggilan alokasi dinamis (`malloc`/`free`) dan operasi salin memori (`memcpy`/`strdup`).
4.  **Menganalisis** implikasi arsitektural dari *Cache Locality*, *Contiguous Memory*, dan *Vectorization (SIMD)* pada pemrosesan string dan buffer raw.
5.  **Mendeteksi, Mengisolasi, dan Memitigasi** anomali memori tingkat rendah seperti *dangling slices*, *unterminated string reads*, dan *unaligned buffer accesses* menggunakan *AddressSanitizer* dan GDB.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari Abstraksi String Tingkat Tinggi ke Byte-Slice Memory
Dalam bahasa tingkat tinggi (seperti Python, Java, atau Go), string dan array adalah objek kelas satu (*first-class citizens*) dengan metadata bawaan (panjang string, kapasitas, *garbage collector headers*). Sistem operasi dan runtime menyembunyikan proses alokasi dan duplikasi memori saat Anda memotong string (`str[a:b]`).

Dalam C, **tidak ada tipe string bawaan**. C hanya mengenal deret kontigu byte di memori yang secara konvensi diakhiri dengan byte null (`\0`). Ketika Anda memproses data masukan jaringan atau file berukuran gigabyte:
*   **Pola Pikir Naif (Deep-Copy / Tokenizing):** Menggunakan `strtok()`, `strdup()`, atau `malloc()` setiap kali token baru ditemukan. Pola ini memicu fragmentasi heap, *cache thrashing*, dan beban alokasi CPU yang masif.
*   **Pola Pikir Sistem Berkinerja Tinggi (Zero-Copy):** Memori dipandang sebagai satu kesatuan pita biner (*contiguous byte buffer*). Kita tidak pernah menyalin data; kita hanya mengarahkan pointer ke titik awal suatu segmen dan mencatat panjangnya (*offset + length*).

```
   TRADISIONAL (Deep-Copy)           ZERO-COPY (String Slices)
   
   Raw Buffer:                       Raw Buffer (Read-Only / In-Place):
   ["GET /index.html HTTP/1.1"]      ["GET /index.html HTTP/1.1"]
            |                                  ^       ^
     Alokasi Baru di Heap                      |       |
     malloc() + memcpy()                       +-------+-- Slice: {ptr, len=11}
            v                                  (Tanpa alokasi heap baru)
   Heap: ["/index.html\0"]
```

Dengan mengadopsi mental model *Zero-Copy*, Anda memandang pointer bukan hanya sebagai alamat tujuan dereferensi, melainkan sebagai penanda koordinat dalam ruang memori fisik.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah perbandingan arsitektural antara arsitektur pemrosesan data tradisional berbasis salin-ulang (*Alloc & Copy*) dengan arsitektur pemrosesan tanpa salinan (*Zero-Copy Engine*).

```
==========================================================================
                 ARSITEKTUR TRADISIONAL (Alloc & Copy)
==========================================================================
 Kernel Space           User Space (Heap Allocation Cascade)
[NIC / Socket] ---> [Kernel Buf] ---> read() ---> [App Read Buffer]
                                                         |
                           +-----------------------------+
                           | parse_token() -> malloc() + memcpy()
                           v
                     [Token 1: Heap] -> Membutuhkan free()
                     [Token 2: Heap] -> Membutuhkan free()
                     [Token 3: Heap] -> Membutuhkan free()
       (Menyebabkan latency tinggi, overhead syscall, dan fragmentasi heap)

==========================================================================
                 ARSITEKTUR ZERO-COPY BUFFER PROCESSING
==========================================================================
 Kernel Space           User Space (Pointer Arithmetic & Windowing)
[NIC / Socket] ---> [Ring Buffer / MMAP Memory]
                           |
                           +-- Direct In-Place Access
                           v
               [ ZERO-COPY PARSER ENGINE ]
                           |
            +--------------+--------------+
            |                             |
     Slice/View A                  Slice/View B
  { .ptr = 0x1004,              { .ptr = 0x100E,
    .len = 4 }                    .len = 10 }
            |                             |
            +--------------+--------------+
                           v
              Direct Processing Core
      (Zero Malloc | Zero Copy | Single Cache-Line Hit)
```

### Diagram Alur Penelusuran Buffer (State-Machine Slicing)

```
[Mulai Buffer]
     |
     v
[Scan Non-Delimiter] -----> Simpan Alamat Awal (`slice.ptr = current`)
     |
     v
[Iterasi Pointer] --------> Geser pointer (`current++`) hingga delimiter ditemukan
     |
     v
[Hitung Jarak] -----------> `slice.len = current - slice.ptr`
     |
     v
[Simpan ke Struct Slice] -> Tidak ada alokasi, tidak ada `\0` yang disisipkan!
     |
     v
[Lompat Delimiter] -------> `current++` -> Lanjut ke segmen berikutnya
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi Array vs Pointer
Array di dalam C adalah blok memori kontinu tunggal yang dialokasikan secara statis, otomatis (stack), atau dinamis. 

```
Deklarasi: char arr[8] = {'A', 'B', 'C', 'D', 'E', 'F', 'G', '\0'};
Memori:    [ 0x41 ][ 0x42 ][ 0x43 ][ 0x44 ][ 0x45 ][ 0x46 ][ 0x47 ][ 0x00 ]
Alamat:     0x1000  0x1001  0x1002  0x1003  0x1004  0x1005  0x1006  0x1007
```

*   `sizeof(arr)` mengevaluasi ukuran total alokasi: `8 * sizeof(char) = 8 byte`.
*   `&arr` menghasilkan tipe `char (*)[8]` (pointer to an array of 8 chars), dengan nilai numerik basis `0x1000`.

### 2. Mekanisme Array Decay
Ketika array dievaluasi dalam ekspresi (kecuali sebagai operan dari operator `sizeof`, unary `&`, atau inisialisasi string literal), array tersebut **meluruh (decay)** menjadi pointer ke elemen pertamanya:

$$\text{Tipe: } T[N] \xrightarrow{\text{decay}} T*$$

```c
void inspect(char *ptr) {
    // Di sini, ptr HANYA sebuah alamat mesin (register CPU atau 8 byte di stack).
    // Metadata ukuran N HILANG secara total. sizeof(ptr) == 8 (pada sistem 64-bit).
}
```

### 3. Idiom String C (Null-Terminated Array of Bytes)
C string adalah konvensi logika, bukan tipe data fisik.
*   Panjang string dihitung secara *linear scan* $\mathcal{O}(N)$ sampai byte bernilai `0x00` ditemukan.
*   Bahaya intrinsik: Jika byte `\0` hilang akibat korupsi memori atau mutasi liar, pembacaan string akan terus menembus batas alokasi (*read overrun*) hingga menabrak halaman memori tak terpetakan (*Segmentation Fault*).

### 4. Struktur Internal Zero-Copy Slice (`string_view`)
Untuk melepaskan ketergantungan pada terminator null (`\0`), kita menyematkan metadata panjang eksplisit pada segmen memori:

```c
typedef struct {
    const char *data; // Alamat elemen pertama (hanya referensi, bukan pemilik)
    size_t len;       // Panjang segmen dalam byte (tanpa mengharuskan null-terminator)
} str_view_t;
```

Ukuran struct ini selalu deterministik: 16 byte pada sistem 64-bit (8 byte pointer + 8 byte length).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Pointer Arithmetic dan Skalasi Tipe
Pointer arithmetic dalam C secara otomatis diskalakan dengan ukuran tipe data target (`sizeof(*ptr)`).

Jika $P$ adalah pointer ke tipe $T$, maka:
$$\text{Alamat Baris Memori}(P + i) = \text{Alamat Asli}(P) + (i \times \text{sizeof}(T))$$

Untuk `char*` atau `uint8_t*`, skalasi bernilai 1. Ini menjadikannya unit standar untuk manipulasi biner *byte-by-byte*.

### 2. Cache Locality dan TLB Performance
CPU modern mentransfer data dari RAM ke cache L1/L2/L3 dalam bentuk *cache lines* (umumnya berukuran 64 byte). 

*   **Pola Akses Kontigu (Zero-Copy):** Saat Anda membaca buffer berukuran 1024 byte secara in-place, satu kali *cache miss* memuat 64 byte data berikutnya. Algoritma traversing sequential memanfaatkan perangkat keras *hardware prefetcher* CPU secara optimal.
*   **Pola Akses Deep-Copy/Malloc:** Setiap kali `strdup()` dipanggil, alokator heap (`glibc ptmalloc`) mencari blok memori bebas, memperbarui chunk headers, dan mengembalikan alamat baru. Pointer-pointer hasil parsing tersebar secara acak di heap (*heap fragmentation*), memicu *TLB misses* dan *cache line invalidations*.

```
Contiguous Buffer:
[Cache Line 0: 64B][Cache Line 1: 64B][Cache Line 2: 64B] -> Stream Prefetcher Maxima

Heap Dispersed Allocations:
[Addr 0x1040 (64B)] .... [Addr 0x9080 (64B)] .... [Addr 0xF020 (64B)] -> Cache Thrashing
```

### 3. Standard C Pointer Decay Rules (C11 §6.3.2.1)
Berdasarkan dokumen C11 spesifikasi ISO/IEC 9899:2011:
> *"Except when it is the operand of the sizeof operator, the _Alignof operator, or the unary & operator, or is a string literal used to initialize an array, an expression that has type 'array of type' is converted to an expression with type 'pointer to type' that points to the initial element of the array object and is not an lvalue."*

Ini menjelaskan mengapa:
```c
char a[10];
char *p = a;       // Legal: decay terjadi
char (*pa)[10] = &a; // Legal: decay TIDAK terjadi karena operator unary &
```

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode dasar yang mendemonstrasikan:
1.  Perbedaan array decay vs array reference.
2.  Pointer walking string idiom.
3.  Konstruksi *Zero-Copy String View*.

```c
#include <stdio.h>
#include <stddef.h>
#include <stdbool.h>

/* Struktur Abstraksi Zero-Copy View */
typedef struct {
    const char *data;
    size_t len;
} str_view_t;

/* Helper untuk membuat slice dari string literal atau raw pointer */
str_view_t str_view_create(const char *str, size_t len) {
    return (str_view_t){ .data = str, .len = len };
}

/* Membandingkan dua string view tanpa dependensi null-terminator */
bool str_view_equals(str_view_t a, str_view_t b) {
    if (a.len != b.len) {
        return false;
    }
    for (size_t i = 0; i < a.len; ++i) {
        if (a.data[i] != b.data[i]) {
            return false;
        }
    }
    return true;
}

/* Demonstrasi Pointer Walking untuk menghitung panjang tanpa strlen() */
size_t custom_strlen_pointer_walk(const char *s) {
    const char *p = s;
    while (*p != '\0') {
        p++;
    }
    return (size_t)(p - s); // Pointer subtraction menghasilkan ptrdiff_t
}

int main(void) {
    /* 1. Anatomi Array Decay */
    char stack_array[32] = "System Architecture in C";
    char *decayed_ptr = stack_array;

    printf("[DECAY TEST]\n");
    printf("sizeof(stack_array) : %zu byte (Ukuran asli seluruh blok memori)\n", sizeof(stack_array));
    printf("sizeof(decayed_ptr) : %zu byte (Ukuran pointer mesin 64-bit)\n\n", sizeof(decayed_ptr));

    /* 2. Pointer Walking */
    printf("[POINTER WALKING TEST]\n");
    size_t len = custom_strlen_pointer_walk(stack_array);
    printf("Calculated Length   : %zu\n\n", len);

    /* 3. Zero-Copy Slicing */
    printf("[ZERO-COPY SLICING]\n");
    // Ambil kata "Architecture" tanpa malloc, tanpa modifikasi sumber buffer.
    // Indeks kata "Architecture": offset 7, panjang 12 byte.
    str_view_t slice = str_view_create(stack_array + 7, 12);

    str_view_t target = str_view_create("Architecture", 12);

    printf("Extracted Slice     : '%.*s'\n", (int)slice.len, slice.data);
    printf("Is Equal to Target? : %s\n", str_view_equals(slice, target) ? "YES" : "NO");

    return 0;
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah diseksi teknis dari kode implementasi fundamental di Seksi 07:

*   **Baris 8–11 (`typedef struct { ... } str_view_t;`)**: Mendefinisikan tipe komposit yang membungkus pointer konstan `const char *data` dan `size_t len`. Penggunaan `const` menjamin immutability; fungsi yang menerima struct ini dilarang keras memodifikasi buffer asal.
*   **Baris 14–16 (`str_view_create`)**: Menggunakan *C99 Compound Literal* syntax `(str_view_t){ ... }` untuk mengembalikan struct langsung melalui register CPU tanpa alokasi heap.
*   **Baris 19–28 (`str_view_equals`)**:
    *   `if (a.len != b.len) return false;`: Optimasi jalur cepat $\mathcal{O}(1)$. Jika ukuran berbeda, komparasi karakter di-bypass sepenuhnya.
    *   `if (a.data[i] != b.data[i])`: Membandingkan byte langsung via indexing. Tidak rentan terhadap ketiadaan karakter `\0` karena loop dikendalikan mutlak oleh batasan eksplisit `.len`.
*   **Baris 31–37 (`custom_strlen_pointer_walk`)**:
    *   `const char *p = s;`: Menginisialisasi pointer iterator `p` pada alamat awal string `s`.
    *   `while (*p != '\0') p++;`: Loop menelusuri memori byte demi byte. Instruksi assembly yang dihasilkan setara dengan *test-and-branch*.
    *   `return (size_t)(p - s);`: Pengurangan dua pointer (`p - s`) menghasilkan tipe bertanda `ptrdiff_t` yang menunjukkan jarak elemen di antara keduanya. Ini di-cast secara aman ke `size_t`.
*   **Baris 41–46 (`stack_array` vs `decayed_ptr`)**: Membuktikan compiler C memperlakukan `sizeof(stack_array)` berdasarkan informasi tabel simbol (32 byte), sedangkan saat di-assign ke `decayed_ptr`, compiler melepaskan metadata array dan memperlakukannya murni sebagai alamat memori 64-bit biasa (8 byte).
*   **Baris 54 (`str_view_create(stack_array + 7, 12)`)**: Pointer arithmetic `stack_array + 7` menggeser alamat basis sebesar $7 \times \text{sizeof}(char)$ byte. Ini memotong sub-string secara instan dalam kompleksitas $\mathcal{O}(1)$.
*   **Baris 58 (`printf("Extracted Slice: '%.*s'\n", ...)`)**: Pemanfaatan format specifier POSIX/C standar `%.*s`. Asterisk (`*`) memerintahkan `printf` mengambil argumen presisi berupa integer (`(int)slice.len`) yang menentukan batas maksimal byte yang dicetak, menghilangkan keharusan string memiliki terminator `\0`.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Edge HTTP Ingestion Engine
Pada server edge computing berskala tinggi (seperti NGINX, Envoy, atau custom API Gateway), server menerima puluhan ribu HTTP Request Line per detik via socket:

```http
GET /api/v1/telemetry/nodes?status=active HTTP/1.1\r\n
Host: gateway.internal\r\n
User-Agent: SensorNode/4.2\r\n
```

### Masalah Pola Tradisional:
Pendekatan naif menggunakan fungsi standar libc seperti `sscanf()` atau kombinasi `strchr()` + `strdup()`:
1.  Setiap token (`Method`, `Path`, `Query String`, `Protocol Version`) dialokasikan terpisah menggunakan `malloc()`.
2.  Terjadi minimal 4 alokasi heap per HTTP request.
3.  Pada beban 100.000 RPS, sistem memanggil alokator memori 400.000 kali per detik.
4.  Dampaknya: Fragmentasi *glibc arena*, *CPU lock contention* pada heap allocator thread-safety, dan *cache pollution*.

### Solusi Zero-Copy Tokenizer:
Kita membaca seluruh frame TCP langsung ke dalam *linear ring buffer* statis. Sebuah parser deterministik berbasis status (State-Machine) menelusuri buffer tersebut dan memproduksi token-token hanya dalam format `str_view_t`. Tidak ada satu byte pun yang dialokasikan di heap, dan data tidak pernah disalin ulang.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah kode produksi C99 untuk modul parser HTTP Request Line berkinerja tinggi yang sepenuhnya menerapkan prinsip **Zero-Copy Memory Processing**.

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stddef.h>

/* Struktur Data Zero-Copy String View */
typedef struct {
    const char *data;
    size_t len;
} str_view_t;

/* Struktur HTTP Request Line Tanpa Alokasi Heap */
typedef struct {
    str_view_t method;
    str_view_t uri;
    str_view_t path;
    str_view_t query_string;
    str_view_t version;
    bool has_query;
} http_request_line_t;

/* Kode Error Parsing */
typedef enum {
    PARSE_OK = 0,
    PARSE_ERR_EMPTY_BUFFER,
    PARSE_ERR_INVALID_METHOD,
    PARSE_ERR_INVALID_URI,
    PARSE_ERR_INVALID_VERSION,
    PARSE_ERR_MALFORMED
} parse_result_t;

/* Parser Zero-Copy */
parse_result_t parse_http_request_line(const char *buf, size_t buf_len, http_request_line_t *out_req) {
    if (!buf || buf_len == 0 || !out_req) {
        return PARSE_ERR_EMPTY_BUFFER;
    }

    const char *cursor = buf;
    const char *end = buf + buf_len;

    /* 1. Parse METHOD (Delimited by SPACE ' ') */
    const char *method_start = cursor;
    while (cursor < end && *cursor != ' ' && *cursor != '\r' && *cursor != '\n') {
        cursor++;
    }

    if (cursor >= end || *cursor != ' ') {
        return PARSE_ERR_INVALID_METHOD;
    }

    out_req->method.data = method_start;
    out_req->method.len = (size_t)(cursor - method_start);

    /* Lewati Spasi */
    cursor++;

    /* 2. Parse URI (Delimited by SPACE ' ') */
    const char *uri_start = cursor;
    while (cursor < end && *cursor != ' ' && *cursor != '\r' && *cursor != '\n') {
        cursor++;
    }

    if (cursor >= end || *cursor != ' ') {
        return PARSE_ERR_INVALID_URI;
    }

    out_req->uri.data = uri_start;
    out_req->uri.len = (size_t)(cursor - uri_start);

    /* Sub-parsing URI: Pisahkan Path dan Query String */
    const char *qmark = NULL;
    for (size_t i = 0; i < out_req->uri.len; ++i) {
        if (out_req->uri.data[i] == '?') {
            qmark = &out_req->uri.data[i];
            break;
        }
    }

    if (qmark) {
        out_req->path.data = out_req->uri.data;
        out_req->path.len = (size_t)(qmark - out_req->uri.data);
        out_req->query_string.data = qmark + 1;
        out_req->query_string.len = (size_t)(out_req->uri.data + out_req->uri.len - (qmark + 1));
        out_req->has_query = true;
    } else {
        out_req->path = out_req->uri;
        out_req->query_string.data = NULL;
        out_req->query_string.len = 0;
        out_req->has_query = false;
    }

    /* Lewati Spasi */
    cursor++;

    /* 3. Parse HTTP VERSION (Delimited by \r\n or \n) */
    const char *version_start = cursor;
    while (cursor < end && *cursor != '\r' && *cursor != '\n') {
        cursor++;
    }

    if (version_start == cursor) {
        return PARSE_ERR_INVALID_VERSION;
    }

    out_req->version.data = version_start;
    out_req->version.len = (size_t)(cursor - version_start);

    /* Validasi akhiran CRLF minimal */
    if (cursor < end && *cursor == '\r') {
        cursor++;
    }
    if (cursor >= end || *cursor != '\n') {
        return PARSE_ERR_MALFORMED;
    }

    return PARSE_OK;
}

/* Logging Observer Utility */
void print_http_request(const http_request_line_t *req) {
    printf("=== PARSED HTTP REQUEST (ZERO-COPY) ===\n");
    printf("Method       : %.*s\n", (int)req->method.len, req->method.data);
    printf("Full URI     : %.*s\n", (int)req->uri.len, req->uri.data);
    printf("Path         : %.*s\n", (int)req->path.len, req->path.data);
    if (req->has_query) {
        printf("Query String : %.*s\n", (int)req->query_string.len, req->query_string.data);
    } else {
        printf("Query String : (None)\n");
    }
    printf("Version      : %.*s\n", (int)req->version.len, req->version.data);
    printf("=======================================\n\n");
}

int main(void) {
    /* Simulasi Raw Buffer Paket Jaringan TCP yang Diterima Socket */
    char raw_network_buffer[] = 
        "POST /api/v2/telemetry/nodes?auth=token123&verbose=true HTTP/1.1\r\n"
        "Host: api.edge.internal\r\n"
        "Content-Type: application/json\r\n\r\n";

    size_t buffer_length = sizeof(raw_network_buffer) - 1; // Exclude \0 sistem

    http_request_line_t request;
    parse_result_t result = parse_http_request_line(raw_network_buffer, buffer_length, &request);

    if (result == PARSE_OK) {
        print_http_request(&request);
    } else {
        fprintf(stderr, "Parsing failed with error code: %d\n", result);
        return EXIT_FAILURE;
    }

    /* Validasi: Memverifikasi kesamaan tanpa modifikasi buffer */
    str_view_t expected_method = { .data = "POST", .len = 4 };
    if (request.method.len == expected_method.len &&
        memcmp(request.method.data, expected_method.data, 4) == 0) {
        printf("[ASSERTION PASSED] Method corresponds directly to source pointer.\n");
    }

    return EXIT_SUCCESS;
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih antara alokasi deep-copy konvensional dan arsitektur *Zero-Copy Buffer Slicing* menuntut evaluasi trade-off sistem berikut:

| Parameter Evaluasi | Pola Tradisional (`malloc` + `strdup`) | Zero-Copy Slice (`str_view_t`) |
| :--- | :--- | :--- |
| **Alokasi Heap (Overhead)** | Sangat Tinggi: Setiap komponen string membutuhkan alokasi memori baru. | **Nol:** Sepenuhnya berjalan di atas stack / register CPU. |
| **Throughput & Latency** | Rendah: Latensi bervariasi bergantung pada beban kerja alokator C (*ptmalloc* locks). | **Deterministik & Ekstrem:** Memproses data secepat CPU mampu membaca alamat RAM. |
| **Penggunaan Memori (Footprint)**| Membutuhkan penggandaan memori ($2\times$ ukuran payload asli atau lebih). | Ringkas: Hanya pointer ($8\text{ byte}$) + panjang ($8\text{ byte}$). |
| **Manajemen Siklus Hidup (Lifetime)**| Sederhana namun lambat: Setiap token independen secara siklus hidup. | **Kritis & Kompleks:** Slice tidak boleh hidup melebihi (*outlive*) buffer induk. |
| **Kompatibilitas Standard Library**| Langsung: Dapat dioperkan ke sembarang fungsi libc (`printf("%s")`, `fopen()`).| Terbatas: Membutuhkan format specifier eksplisit (`%.*s`) atau konversi manual. |
| **Risiko Keamanan Data Mutasi** | Aman: Modifikasi token terisolasi dan tidak merusak buffer sumber. | **Rentan Kerusakan:** Jika buffer asal tidak `const`, satu mutasi merusak seluruh slice. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

Dalam arsitektur Zero-Copy, kelalaian mikro dapat memicu kerentanan eksploitasi atau *silent undefined behaviors*:

### 1. The Dangling Slice (Akses Memori Liar)
*   **Kasus:** Suatu fungsi mengembalikan struct `str_view_t` yang menunjuk ke array lokal yang dialokasikan di dalam stack frame fungsi tersebut.
*   **Dampak:** Segera setelah fungsi kembali (*returns*), stack frame hancur. Pointer dalam `str_view_t` kini menunjuk ke *garbage data*.
*   **Mitigasi:** Pasang atribut kompilator GCC/Clang `__attribute__((warn_unused_result))` dan pastikan secara arsitektural sumber data hanya berasal dari arena/buffer yang masa hidupnya lebih panjang daripada siklus pengolahan data.

### 2. Bahaya Operasi Standard String (`strlen`, `strcpy`) pada Slice
*   **Kasus:** Mengoperasikan fungsi string libc berbasis anggapan `\0` terhadap `str_view_t.data`.
*   **Dampak:** Buffer overrun masif. Fungsi pembacaan melampaui panjang logis slice dan terus membaca hingga menemukan nilai byte `0x00` acak di memori, berpotensi membocorkan data sensitif (*Information Disclosure*) atau crash.

### 3. Delimiter Berurutan dan Zero-Length Slice
*   **Kasus:** URI yang mengandung spasi ganda atau format malformed seperti `GET  /path HTTP/1.1`.
*   **Dampak:** Pointer start dan pointer end bernilai identik, menghasilkan `len = 0`. Kode yang tidak memvalidasi `len > 0` sebelum dereferensi `slice.data[0]` akan melakukan akses ilegal jika buffer dasar berukuran 0.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Menghitung Ukuran Pointer Menggunakan `sizeof()`
```c
// SALAH
void parse_data(char buffer[256]) {
    size_t len = sizeof(buffer); // BUG: Selalu mengembalikan 8 pada mesin 64-bit!
}

// BENAR
void parse_data(const char *buffer, size_t buffer_len) {
    size_t len = buffer_len; // Ukuran eksplisit dikirim sebagai parameter
}
```

### Kesalahan 2: Memodifikasi String Literal
```c
// SALAH: undefined behavior (SIGSEGV)
char *str = "HELLO WORLD";
str[0] = 'h'; 

// BENAR: Array stack dapat dimodifikasi secara lokal
char str[] = "HELLO WORLD";
str[0] = 'h';
```

### Kesalahan 3: Off-by-One Saat Menyisipkan Terminator Manual
```c
// SALAH
char buf[4];
// "TEST" membutuhkan 5 byte (4 karakter + 1 null terminator)
strncpy(buf, "TEST", 4);
printf("%s\n", buf); // BUG: Buffer overrun, tidak ada '\0' di akhir!

// BENAR
char buf[5];
memcpy(buf, "TEST", 4);
buf[4] = '\0';
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Const-Correctness:** Dalam zero-copy buffer processing, semua view **wajib** menggunakan pointer berkualifikasi const (`const char *data`). Ini mencegah *in-place contamination* data oleh sub-komponen parsing secara aksidental.
2.  **Explicit Fat-Pointer Convention:** Jangan pernah mengoper pointer raw string secara telanjang tanpa panjangnya kecuali dijamin berakhiran null. Selalu gunakan pola *Fat-Pointer* (pasangan alamat dan ukuran) yang dibungkus dalam representasi struct tunggal.
3.  **Hindari Pemanggilan Fungsi Berbahaya:** Singkirkan `strcat()`, `strcpy()`, dan `sprintf()`. Gunakan representasi slice dengan format `%.*s` atau fungsi tersanitasi seperti `snprintf()`.
4.  **Enforce Compiler Warnings:** Proyek sistem wajib dikompilasi dengan bendera ketat:
    ```bash
    -Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror
    ```

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Vectorization dan Akselerasi Hardware (SIMD)
Ketika Anda melakukan scanning terhadap delimiter pada buffer besar (misal: mencari byte `\r` atau spasi ` `), pemindaian byte-by-byte menggunakan instruksi skalar konvensional membutuhkan satu cycle per byte.

Dengan memanfaatkan intrinsik SIMD (AVX2 pada arsitektur x86_64), Anda dapat memproses 32 byte sekaligus dalam **satu instruksi clock CPU**:

```c
#include <immintrin.h>

/* Scan byte tertentu pada buffer menggunakan AVX2 (32 Byte per Iterasi) */
const char* avx2_find_char(const char* buf, size_t len, char target) {
    const char *p = buf;
    __m256i target_vec = _mm256_set1_epi8(target);

    while (len >= 32) {
        __m256i chunk = _mm256_loadu_si256((const __m256i*)p);
        __m256i cmp = _mm256_cmpeq_epi8(chunk, target_vec);
        unsigned int mask = (unsigned int)_mm256_movemask_epi8(cmp);

        if (mask != 0) {
            // Karakter ditemukan dalam 32 byte ini!
            // __builtin_ctz menghitung trailing zeros untuk menentukan offset tepat
            return p + __builtin_ctz(mask);
        }

        p += 32;
        len -= 32;
    }

    /* Fallback skalar untuk sisa buffer */
    while (len > 0) {
        if (*p == target) return p;
        p++;
        len--;
    }

    return NULL;
}
```

*Keuntungan:* Mengurangi waktu pencarian delimiter pada paket berukuran jumbo (9000 bytes MTU) hingga $\approx 85\%$.

---

# SEKSI 16 — KEAMANAN & HARDENING

Arsitektur Zero-Copy menuntut pertahanan defensif tinggi terhadap manipulasi batasan memori.

### 1. Pointer Boundary Validation Invariant
Setiap kali melakukan dereferensi pointer iterator, wajib ditegakkan formula invariant batasan:

$$\text{cursor} + \text{offset} \le \text{buffer\_start} + \text{buffer\_length}$$

Jika kondisi ini tidak terpenuhi, eksekusi wajib dihentikan seketika untuk mencegah *arbitrary out-of-bounds read*.

### 2. Sanitasi Runtime Menggunakan AddressSanitizer (ASan)
Kompilasi source code sistem pengolah buffer menggunakan Clang/GCC dengan flag instrumentasi deteksi bug memori:

```bash
gcc -std=c11 -O1 -g -fsanitize=address -fsanitize=undefined -fno-omit-frame-pointer parser.c -o parser
```

ASan akan menyuntikkan *redzones* di sekeliling alokasi buffer dan memeriksa integritas shadow memory pada setiap akses pointer dereferencing. Setiap pelanggaran batasan memori akan memicu laporan instan (*ASan crash dump*).

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Hexdump Memory Diagnostic Utility
Dalam debugging level rendah, cetak layout memori aktual untuk memverifikasi lokasi pointer terhadap segmentasi memory pool:

```c
void debug_dump_buffer_window(const char *title, const char *ptr, size_t len) {
    fprintf(stderr, "=== [DEBUG WINDOW: %s] Addr: %p, Len: %zu ===\n", title, (const void*)ptr, len);
    for (size_t i = 0; i < len; ++i) {
        unsigned char c = (unsigned char)ptr[i];
        fprintf(stderr, "%02X ", c);
        if ((i + 1) % 16 == 0) fprintf(stderr, "\n");
    }
    fprintf(stderr, "\n======================================================\n");
}
```

### 2. Pemeriksaan Register dan Slice pada GDB
Ketika melakukan debugging aplikasi C yang terhenti akibat segmentation fault:

```gdb
(gdb) print my_slice
$1 = {data = 0x7fffffffe340 "GET /index.html", len = 3}

# Memeriksa data aktual sepanjang N byte pada alamat pointer slice
(gdb) x/3sb my_slice.data
0x7fffffffe340: "GET"

# Memeriksa representasi byte heksadesimal langsung dari pointer
(gdb) x/8xb my_slice.data
0x7fffffffe340: 0x47  0x45  0x54  0x20  0x2f  0x69  0x6e  0x64
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+------------------------------------------------------------------------------------+
|                         C ARRAY & ZERO-COPY CHEAT SHEET                            |
+------------------------------------------------------------------------------------+
| SINTAKS/EKSPRESI      | MAKNA ARSITEKTURAL / KOMPILATOR                            |
+------------------------------------------------------------------------------------+
| sizeof(arr)           | Ukuran total array dalam byte (HANYA pada scope deklarasi) |
| sizeof(ptr)           | Ukuran alamat mesin register (8 byte pada sistem 64-bit)   |
| ptr + i               | Alamat = ptr + (i * sizeof(*ptr))                          |
| ptr2 - ptr1           | Menghasilkan ptrdiff_t (jumlah elemen antara 2 pointer)    |
| %.*s                  | printf specifier untuk slice: butuh (int)len dan char* ptr |
| str_view_t            | Fat pointer: { const char *data; size_t len; }             |
+------------------------------------------------------------------------------------+
| ATURAN EMAS MEMORY SLICING:                                                        |
| 1. Slice TIDAK PERNAH memiliki hak milik atas data (Non-owning reference).         |
| 2. Slice DILARANG HIDUP lebih lama daripada masa aktif buffer dasarnya.            |
| 3. Jangan pernah mengasumsikan adanya terminator '\0' pada sub-slice pointer.      |
+------------------------------------------------------------------------------------+
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)
1. **Apa tipe data hasil evaluasi ekspresi `&arr` jika diketahui `int arr[10];`?**  
   *Jawaban:* Tipenya adalah pointer ke array dari 10 integer: `int (*)[10]`, bukan `int**`.

2. **Kapan suatu array C TIDAK meluruh (decay) menjadi sebuah pointer?**  
   *Jawaban:* Ketika menjadi operan dari operator `sizeof`, unary `&` (address-of), `_Alignof`, atau ketika string literal digunakan untuk menginisialisasi array karakter secara langsung.

3. **Mengapa pemanggilan fungsi `strlen(slice.data)` dapat menghasilkan eksploitasi keamanan atau crash pada arsitektur Zero-Copy?**  
   *Jawaban:* Karena `slice.data` menunjuk ke segmen memori tanpa jaminan adanya karakter penutup null `\0` pada akhir panjang segmen logisnya, memicu *out-of-bounds read*.

4. **Berapa ukuran memori dari struct `struct { const char *ptr; size_t len; }` pada arsitektur modern x86_64?**  
   *Jawaban:* 16 byte (8 byte untuk pointer alamat 64-bit + 8 byte untuk unsigned integer 64-bit `size_t`).

5. **Apa fungsi penanda presisi `.*` pada format string `printf("%.*s", len, ptr)`?**  
   *Jawaban:* Memerintahkan `printf` membatasi pembacaan karakter dari pointer hanya sampai sejumlah `len` byte, mengabaikan pencarian karakter null-terminator.

### Soal Tingkat Menengah (Intermediate)
6. **Diberikan kode berikut:**
   ```c
   str_view_t get_segment() {
       char local_buf[] = "PAYLOAD-DATA";
       return (str_view_t){ .data = local_buf, .len = 12 };
   }
   ```
   **Jelaskan secara presisi anomali memori apa yang terjadi jika fungsi ini dieksekusi!**  
   *Jawaban:* Terjadi kondisi *Dangling Pointer*. `local_buf` dialokasikan di dalam stack frame fungsi `get_segment()`. Ketika fungsi kembali (*returns*), frame stack tersebut diinvalidasi. Struct yang dikembalikan kini menunjuk ke alamat memori yang tidak valid atau telah tertimpa (*undefined behavior* jika diakses).

7. **Bagaimana cara aman mengimplementasikan fungsi komparasi string case-insensitive pada struktur `str_view_t` tanpa menggunakan fungsi libc `strcasecmp`?**  
   *Jawaban:* Bandingkan panjang terlebih dahulu. Jika panjang sama, lakukan looping terikat `len` dengan mengonversi tiap karakter ke lowercase menggunakan `tolower((unsigned char)c)` satu per satu tanpa bergantung pada karakter null terminator.

8. **Mengapa pointer subtraction (`p2 - p1`) hanya diizinkan secara legal menurut standar C jika kedua pointer menunjuk ke array yang sama?**  
   *Jawaban:* Standar C menyatakan bahwa operasi aritmatika dan relasional antar pointer hanya didefinisikan jika keduanya menunjuk ke elemen dalam objek array yang sama (atau satu elemen melewati batas akhir array). Pengurangan pointer dari dua objek alokasi berbeda menghasilkan *Undefined Behavior* karena tata letak relatif antar objek di memori virtual tidak terikat kontrak formal bahasa.

9. **Apa implikasi performa penggunaan `memchr()` bawaan glibc dibandingkan loop skalar `while(*p != target)` dalam mencari delimiter zero-copy?**  
   *Jawaban:* Implementasi `memchr()` dalam glibc telah dioptimasi secara manual menggunakan instruksi bahasa rakitan (assembly) yang memanfaatkan SIMD (seperti AVX2/AVX-512 atau ARM NEON), membaca data per 32/64-byte sekaligus per siklus clock, jauh melampaui loop skalar byte-by-byte.

10. **Bagaimana pola Zero-Copy memengaruhi beban kerja Kernel-to-User Space context switching saat membaca file berukuran besar?**  
    *Jawaban:* Ketika zero-copy dikombinasikan dengan syscall `mmap()`, buffer file langsung dipetakan ke dalam virtual memory space proses pengguna. Parser zero-copy membaca data langsung dari cache halaman kernel (*Page Cache*) tanpa duplikasi memori melalui perantara syscall `read()`, menurunkan *context switches* dan mengeliminasi alokasi ganda di memory space.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: High-Speed In-Place JSON Key-Value Tokenizer

#### Deskripsi
Rancang dan bangun sebuah parser mikro JSON satu tingkat (*flat JSON object parser*) yang memproses string berformat JSON langsung dari buffer mentah tanpa menggunakan `malloc()` sekalipun, dan menghasilkan representasi key-value pair dalam format Zero-Copy String View.

#### Persyaratan Fungsional:
1.  **Dilarang Alokasi Dinamis:** Kode sumber tidak boleh memanggil `malloc`, `calloc`, `realloc`, `free`, maupun `strdup`.
2.  **Spesifikasi Input Buffer:** Program menerima raw payload ASCII/UTF-8 JSON datar di memori, misalnya:
    ```json
    {"sensor_id":"SN-9021","temperature":24.58,"status":"ONLINE","region":"ap-southeast"}
    ```
3.  **Representasi Data:** Bangun struktur data:
    ```c
    typedef struct {
        str_view_t key;
        str_view_t value;
    } json_kv_t;
    ```
4.  **Ekstraksi Deterministik:** Implementasikan fungsi:
    ```c
    size_t parse_json_flat(const char *json_buf, size_t len, json_kv_t *out_entries, size_t max_entries);
    ```
    Fungsi ini harus mampu mengekstrak seluruh pasangan key-value ke dalam array `out_entries` tanpa merusak integritas buffer sumber (buffer sumber harus `const char*`).
5.  **Dukungan Tipe Nilai:** Parser harus mampu membedakan string (terbungkus tanda kutip `"..."`) dan literal angka/boolean (tanpa tanda kutip). Tanda kutip pembungkus string **tidak boleh** disertakan ke dalam `.data` dari `str_view_t` yang dihasilkan.

#### Tolok Ukur Keberhasilan (Verification Test):
*   Lulus kompilasi bersih tanpa *warning* menggunakan opsi:
    ```bash
    gcc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined praktikum.c -o praktikum
    ```
*   Dijalankan terhadap payload JSON berukuran 100 KB yang berulang, program menyelesaikan parsing dalam waktu kurang dari 2 milidetik tanpa memicu kebocoran memori atau peringatan runtime AddressSanitizer.
*   Pemeriksaan GDB menunjukkan seluruh alamat `out_entries[i].key.data` secara strictly mereferensikan offset memori di dalam alamat basis raw input buffer.