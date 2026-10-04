# Kurikulum Enterprise C: Rekayasa Sistem Berkinerja Tinggi
## Bab 02: Tipe Data Primitif, Representasi Bit, & Aritmetika Biner
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, software engineer diharapkan mampu:
*   **Menganalisis dan Memprediksi** tata letak memori fisik (*physical memory layout*), *alignment boundary*, *padding*, serta representasi biner dari semua tipe data primitif C11/C17/C23 pada arsitektur x86_64 dan AArch64.
*   **Mengeliminasi Kerentanan Undefined Behavior (UB)** yang bersumber dari *signed integer overflow*, *illegal bit-shifts*, serta pelanggaran *strict aliasing* pada level manipulasi bit.
*   **Mengimplementasikan Algoritma Bit-Level Deterministik** (seperti *bit-twiddling hacks*, operasi *branchless*, deteksi/konversi *endianness*, dan manipulasi mantissa/eksponen IEEE 754) dengan efisiensi siklus instruksi CPU setara assembler.
*   **Mendesain Protokol Biner Kompak (*Zero-Copy Binary Serialization*)** yang aman, portabel, dan bebas dari *memory alignment faults* (SIGBUS) serta *data corruption* akibat heterogenitas perangkat keras produksi.

---

### 2. Prerequisite
*   Pemahaman mendalam mengenai siklus kompilasi C (*Preprocessing, Compilation, Assembly, Linking*) dari Modul 01.
*   Familiaritas dengan representasi bilangan heksadesimal, biner, dan aljabar Boolean dasar.
*   Kemampuan membaca instruksi assembly dasar (x86_64 atau ARM64) untuk memverifikasi keluaran compiler.
*   Akses ke lingkungan Linux berbasis POSIX dengan GCC/Clang dan GDB/LLDB.

---

### 3. Concept & Internal Architecture

#### 3.1 Two's Complement (Komplemen Dua) & Representasi Integer
C23 secara resmi menetapkan representasi *Two's Complement* sebagai standar tunggal bilangan bertanda (*signed integers*), mengakhiri ambiguitas historis sistem *Sign-Magnitude* dan *Ones' Complement*.

Pada sistem $N$-bit Two's Complement:
*   Nilai minimum: $-2^{N-1}$
*   Nilai maksimum: $2^{N-1} - 1$
*   Bit paling signifikan (MSB) merepresentasikan sign bit dengan bobot negatif: $-b_{N-1} \cdot 2^{N-1}$.

$$\text{Nilai} = -b_{N-1}2^{N-1} + \sum_{i=0}^{N-2} b_i 2^i$$

```
Contoh 8-bit Signed Integer:
  Nilai  0 : 0000 0000
  Nilai  1 : 0000 0001
  Nilai -1 : 1111 1111  (-128 + 64 + 32 + 16 + 8 + 4 + 2 + 1 = -1)
  Nilai -128: 1000 0000
  Nilai 127: 0111 1111
```

**Konsekuensi Arsitektural:**
1.  **Asimetri Rentang:** Nilai mutlak dari `INT_MIN` selalu lebih besar 1 unit dibanding `INT_MAX`. Eksekusi `-INT_MIN` menghasilkan *Signed Integer Overflow*, yang memicu **Undefined Behavior (UB)**.
2.  **Modular Arithmetic vs UB:** Tipe *unsigned* dijamin oleh standar C mengimplementasikan aritmetika modular modulo $2^N$ (tidak pernah overflow, melainkan *wrap-around*). Sebaliknya, *signed arithmetic overflow* diasumsikan oleh optimizer compiler tidak akan pernah terjadi, membuka celah eliminasi kode kritis saat optimasi `-O2` atau `-O3`.

#### 3.2 IEEE 754 Floating-Point Standard (Single & Double Precision)
Operasi *floating-point* membagi kata memori (*memory word*) menjadi tiga komponen diskrit:
*   **Sign bit ($S$):** 1 bit (0 untuk positif, 1 untuk negatif).
*   **Biased Exponent ($E$):** Merepresentasikan skala magnitudo dengan penambahan *bias* ($2^{k-1} - 1$).
*   **Normalized Mantissa/Significand ($M$):** Merepresentasikan presisi fraksional dengan implisit bit $1.f$ (pada bilangan ternormalisasi).

$$\text{Nilai} = (-1)^S \times 2^{E - \text{Bias}} \times (1 + \sum_{i=1}^{P} b_{-i} 2^{-i})$$

| Parameter | IEEE 754 Single (`float`) | IEEE 754 Double (`double`) |
| :--- | :--- | :--- |
| **Total Bit** | 32 bit | 64 bit |
| **Sign Bit** | 1 bit [bit 31] | 1 bit [bit 63] |
| **Exponent** | 8 bit [bit 30:23] (Bias: 127) | 11 bit [bit 62:52] (Bias: 1023) |
| **Fraction** | 23 bit [bit 22:0] | 52 bit [bit 51:0] |
| **Machine Epsilon ($\epsilon$)**| $\approx 1.192 \times 10^{-7}$ | $\approx 2.220 \times 10^{-16}$ |

**Status Khusus (Corner Cases):**
*   **Subnormal/Denormalized:** Jika $E = 0$ dan $M \neq 0$. Menghindari *underflow* mendadak (*gradual underflow*), namun dieksekusi lambat secara perangkat keras (*microcode fallback*).
*   **Zero ($\pm 0$):** $E = 0, M = 0$. Tanda membedakan arah limit ($+0.0$ vs $-0.0$).
*   **Infinity ($\pm \infty$):** $E = \text{All 1s}, M = 0$.
*   **NaN (Not a Number):** $E = \text{All 1s}, M \neq 0$. Terbagi menjadi *Quiet NaN* (qNaN) dan *Signaling NaN* (sNaN).

#### 3.3 Data Alignment, Padding, dan Struct Packing
CPU modern membaca memori melalui *memory bus* dalam ukuran blok kata (*bus width*, umumnya 32-bit atau 64-bit). Data primitif berukuran $k$ byte harus dialokasikan pada alamat memori fisik yang merupakan kelipatan dari $k$ (natural alignment boundary).

*   `char` (1 byte): Alignment bebas (kelipatan 1).
*   `uint16_t` (2 byte): Alamat harus genap (kelipatan 2).
*   `uint32_t` / `float` (4 byte): Alamat kelipatan 4.
*   `uint64_t` / `double` / pointer (8 byte): Alamat kelipatan 8.

Compiler C menyisipkan *internal padding* di antara anggota struct dan *tail padding* di akhir struct untuk memastikan array dari struct tersebut mempertahankan alignment setiap elemennya.

#### 3.4 Endianness (Byte Ordering)
Endianness mengatur urutan byte individual dari tipe data multi-byte di alamat memori berurutan:
*   **Little-Endian (x86_64, default ARM64):** Byte paling tidak signifikan (*Least Significant Byte / LSB*) disimpan di alamat memori terendah.
*   **Big-Endian (Network Byte Order, SPARC, IBM z/Architecture):** Byte paling signifikan (*Most Significant Byte / MSB*) disimpan di alamat memori terendah.

---

### 4. Why & What
*   **Mengapa `int` dan `long` berbahaya dalam sistem terdistribusi/embedded?**
    Standar ISO C hanya menentukan ukuran minimum untuk tipe data fundamental. `long` berukuran 32-bit pada arsitektur Windows x86_64 (LLP64), namun berukuran 64-bit pada Linux/macOS x86_64 (LP64). Menggunakan tipe data primitif non-spesifik pada packet header protokol jaringan akan memicu rekonsiliasi memori yang korup saat melintasi batas sistem operasi atau arsitektur.
*   **Apa solusinya?**
    Standardisasi menggunakan ISO C99 `<stdint.h>` (`uint8_t`, `int32_t`, `uint64_t`, `uintptr_t`) dan `<inttypes.h>` untuk format penentu I/O portabel (`PRIu64`, `PRId32`).
*   **Mengapa Bit-Shifting dapat merusak kode produksi?**
    1.  Menggeser tipe data bernilai negatif atau menggeser bit hingga mengubah sign bit adalah UB atau *implementation-defined* pada standar pra-C23.
    2.  Menggeser nilai dengan *count* yang $\ge \text{lebar bit tipe data}$ atau bernilai negatif (contoh: `uint32_t x = 1U << 32;`) adalah **Undefined Behavior murni** pada C, menghasilkan perilaku acak bergantung pada bagaimana instruksi assembly CPU menangani masking pada register register pergeseran (misal: x86 mengabaikan bit di atas 5-bit shift operand melalui instruksi `SHL`, sehingga `1 << 32` menjadi `1 << 0 = 1`).

---

### 5. How (Workflow Detail)

Alur kerja evaluasi, normalisasi, dan serialisasi data biner tingkat rendah:

```
[Inbound Raw Buffer / I/O Port]
              │
              ▼
   [Bounds & Alignment Check] ──────────(Unaligned / Malformed)──┐
              │                                                  │
              ▼ (Valid Size)                                     │
    [Zero-Copy Memory Access]                                    │
   (Menggunakan memcpy/memmove                                   │
    untuk mencegah Type Punning UB)                              │
              │                                                  │
              ▼                                                  │
   [Endianness Transformation]                                   │
 (Host-to-Network: htonl, htobe64)                               │
 (Network-to-Host: ntohl, be64toh)                               │
              │                                                  │
              ▼                                                  │
    [Range & Value Assertion]                                    │
  - Validasi Integer Wrap-around                                 │
  - Deteksi NaN / Inf pada Float                                 │
              │                                                  │
              ▼                                                  │
   [Bitmasking & Safe Arithmetic]                                │
              │                                                  │
              ▼                                                  │
 [Core Domain Processing Engine]                                 │
              │                                                  ▼
              └─────────────────────────────────────────► [Kernel Trap / Error Handler]
```

---

### 6. Analogy & Diagram ASCII

#### 6.1 IEEE 754 Single-Precision Breakdown (32-bit)
```
  Bit: 31    30        23 22                                     0
      ┌───┬──────────────┬────────────────────────────────────────┐
      │ S │   Exponent   │                Mantissa                │
      └───┴──────────────┴────────────────────────────────────────┘
      1-bit     8-bit                       23-bit
     [Sign]  [Bias: 127]             [Implisit 1.xxxx...]
```

#### 6.2 Visualisasi Memory Padding pada Struct
Diberikan struct C berikut:
```c
struct BadLayout {
    uint8_t  a;    // 1 byte
    uint64_t b;    // 8 byte
    uint16_t c;    // 2 byte
    uint32_t d;    // 4 byte
};
```
Representasi Memori Fisik (Ukuran total: 24 byte! Pemborosan 9 byte akibat padding):
```
Alamat: +0   +1   +2   +3   +4   +5   +6   +7
        ┌────┬───────────────────────────────┐
 0x0000 │ a  │      PADDING (7 byte)         │
        ├────┴───────────────────────────────┤
 0x0008 │                b                   │
        ├─────────┬─────────┬────────────────┤
 0x0010 │    c    │ PADDING │       d        │
        └─────────┴─────────┴────────────────┘
```

Rekayasa Ulang Struktur (Optimal Layout - Ukuran total: 16 byte, 0 byte wasted padding):
```c
struct GoodLayout {
    uint64_t b;    // 8 byte (Offset 0)
    uint32_t d;    // 4 byte (Offset 8)
    uint16_t c;    // 2 byte (Offset 12)
    uint8_t  a;    // 1 byte (Offset 14)
    uint8_t  pad;  // 1 byte tail padding (Offset 15) untuk alignment 8-byte
};
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Safe Bitwise Manipulation Toolkit
Implementasi operasi bit fundamental yang bebas dari Undefined Behavior, mengoptimalkan intrinsic compiler jika tersedia.

```c
#include <stdint.h>
#include <stdbool.h>
#include <limits.h>

/* Safe left-shift: Mencegah UB jika shift_count >= lebar tipe */
static inline uint32_t safe_shl_u32(uint32_t value, uint32_t shift_count) {
    if (shift_count >= 32U) {
        return 0U;
    }
    return value << shift_count;
}

/* Branchless circular rotate left (ROL) */
static inline uint32_t rotl32(uint32_t value, uint32_t count) {
    const uint32_t mask = 31U;
    count &= mask;
    return (value << count) | (value >> ((-count) & mask));
}

/* Population Count: Menghitung bit bernilai '1' secara deterministik */
static inline uint32_t safe_popcount32(uint32_t value) {
#if defined(__GNUC__) || defined(__clang__)
    return (uint32_t)__builtin_popcount(value);
#else
    /* Software fallback: SWAR (SIMD Within A Register) */
    value = value - ((value >> 1) & 0x55555555U);
    value = (value & 0x33333333U) + ((value >> 2) & 0x33333333U);
    return (((value + (value >> 4)) & 0x0F0F0F0FU) * 0x01010101U) >> 24;
#endif
}
```

#### 7.2 Practical Example: Enterprise Binary Protocol Serialization
Pustaka penanganan frame protokol biner berkinerja tinggi, zero-copy, endianness-agnostic, dan patuh standar MISRA-C / SEI CERT C.

```c
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <math.h>

#if defined(_WIN32)
    #include <winsock2.h>
#else
    #include <arpa/inet.h>
    #include <endian.h>
#endif

/* Format Definisi Protokol Mesin Telemetri */
typedef struct {
    uint32_t device_id;
    uint16_t status_flags;
    int32_t  temperature_scaled; // Skala fixed-point: Real = temperature_scaled / 1000.0
    float    pressure_psi;
} __attribute__((aligned(8))) TelemetryPayload;

/* Encoding aman: Mengonversi Host Order ke Network Order (Big Endian) */
int serialize_telemetry(const TelemetryPayload *src, uint8_t *dest_buffer, size_t dest_len) {
    if (src == NULL || dest_buffer == NULL || dest_len < 14) {
        return -1; // Buffer tidak memadai atau pointer NULL
    }

    /* Validasi Float: Tolak NaN dan Inf */
    if (isnan(src->pressure_psi) || isinf(src->pressure_psi)) {
        return -2; // Nilai floating-point invalid
    }

    /* 1. Device ID (4-byte) */
    uint32_t net_device_id = htonl(src->device_id);
    memcpy(dest_buffer + 0, &net_device_id, sizeof(net_device_id));

    /* 2. Status Flags (2-byte) */
    uint16_t net_flags = htons(src->status_flags);
    memcpy(dest_buffer + 4, &net_flags, sizeof(net_flags));

    /* 3. Scaled Temperature (4-byte Signed) */
    /* Two's complement representation: Cast bit patterns safely via unsigned */
    uint32_t net_temp = htonl((uint32_t)src->temperature_scaled);
    memcpy(dest_buffer + 6, &net_temp, sizeof(net_temp));

    /* 4. Pressure PSI (4-byte IEEE 754 Float) */
    /* Type punning strictly compliant to ISO C via memcpy */
    uint32_t float_bits;
    memcpy(&float_bits, &src->pressure_psi, sizeof(float_bits));
    uint32_t net_pressure = htonl(float_bits);
    memcpy(dest_buffer + 10, &net_pressure, sizeof(net_pressure));

    return 14; // Jumlah byte ter-serialisasi
}

/* Decoding aman: Mengonversi Network Order ke Host Order */
int deserialize_telemetry(const uint8_t *src_buffer, size_t src_len, TelemetryPayload *dest) {
    if (src_buffer == NULL || dest == NULL || src_len < 14) {
        return -1;
    }

    uint32_t net_device_id;
    memcpy(&net_device_id, src_buffer + 0, sizeof(net_device_id));
    dest->device_id = ntohl(net_device_id);

    uint16_t net_flags;
    memcpy(&net_flags, src_buffer + 4, sizeof(net_flags));
    dest->status_flags = ntohs(net_flags);

    uint32_t net_temp;
    memcpy(&net_temp, src_buffer + 6, sizeof(net_temp));
    dest->temperature_scaled = (int32_t)ntohl(net_temp);

    uint32_t net_pressure;
    memcpy(&net_pressure, src_buffer + 10, sizeof(net_pressure));
    uint32_t host_float_bits = ntohl(net_pressure);
    memcpy(&dest->pressure_psi, &host_float_bits, sizeof(dest->pressure_psi));

    /* Post-condition Check */
    if (isnan(dest->pressure_psi) || isinf(dest->pressure_psi)) {
        return -2;
    }

    return 0;
}
```

---

### 8. Real World Case Study: High-Frequency Trading Market Feed Engine

**Konteks Masalah:**
Sebuah platform High-Frequency Trading (HFT) mengonsumsi bursa saham melalui feed UDP Multicast biner (ITCH Protocol). Volume pemrosesan mencapai 50 juta pesan per detik. Kode lama mengalami insiden crash berkala dan keterlambatan transaksi:
1.  **SIGBUS Fault:** Crash terjadi ketika kode berjalan pada node server ARM64 (AWS Graviton) akibat *dereferencing unaligned pointer* saat melakukan cast raw buffer ke `struct OrderBookEntry*`.
2.  **Float Rounding Error:** Perhitungan spread harga valas menggunakan tipe `double` mengalami kesalahan akumulatif fraksional:
    $$0.1 + 0.2 = 0.3000000000000000444...$$
    Kondisi ini memicu pembatalan eksekusi order otomatis oleh *risk-management engine*.
3.  **Compiler Aggressive Dead Code Elimination:** Kondisi overflow harga dihitung menggunakan aritmetika `int32_t`. GCC dengan optimasi `-O3` mendeteksi bahwa kode memeriksa `if (price + delta < price)` dan **menghapus baris pemeriksaan tersebut** karena signed overflow adalah UB (compiler berasumsi operasi signed tidak pernah meluap).

**Solusi Arsitektur:**
1.  **Eliminasi Struct Direct Cast:** Mengganti parsing struct-in-place berbahaya dengan deserialisasi aman berbasis pergeseran register atau `__builtin_memcpy` (yang diinlining oleh GCC/Clang menjadi instruksi mov register tunggal tanpa overhead pemanggilan fungsi).
2.  **Fixed-Point Numeric Representation:** Mengganti IEEE 754 dengan 64-bit Decimal Fixed-Point berpresisi $10^8$ (menggunakan tipe data dasar `int64_t`). Seluruh operasi desimal dijamin deterministik.
3.  **Builtin Safe Arithmetic:** Menggunakan Clang/GCC integer overflow intrinsics: `__builtin_add_overflow` dan `__builtin_mul_overflow`.

```c
#include <stdint.h>
#include <stdbool.h>

#define PRICE_PRECISION 100000000ULL // 10^8

typedef int64_t fixed_price_t;

/* Operasi aritmetika aman yang kebal dari penghapusan optimizer */
bool safe_add_price(fixed_price_t a, fixed_price_t b, fixed_price_t *result) {
#if __has_builtin(__builtin_add_overflow)
    return !__builtin_add_overflow(a, b, result);
#else
    if ((b > 0 && a > INT64_MAX - b) || (b < 0 && a < INT64_MIN - b)) {
        return false; // Overflow terdeteksi
    }
    *result = a + b;
    return true;
#endif
}
```

---

### 9. Trade-offs: Implementasi Biner Tingkat Rendah

| Strategi / Pendekatan | Pros (Keuntungan) | Cons (Konsekuensi & Biaya) | Skenario Penggunaan Optimal |
| :--- | :--- | :--- | :--- |
| **Bit-Fields (`unsigned int x : 4;`)** | Sintaksis kode intuitif; otomatisasi alokasi bit oleh compiler. | Layout bit bersifat *Implementation-Defined*; performa buruk (read-modify-write cycle overhead); endianness tidak standar. | Komponen hardware driver internal yang tidak pernah diekspor lintas platform. |
| **Manual Bitmask & Shifts** | Deterministik murni lintas arsitektur; portabel; pemetaan biner 1:1 ke register CPU. | Kode verbose; rawan salah tik (*off-by-one errors*); membutuhkan dokumentasi mask yang ketat. | Protokol Jaringan (TCP/IP, FIX/FAST), driver hardware register level enterprise. |
| **`#pragma pack(push, 1)`** | Memory footprint struct minimal; parsing payload eksternal langsung. | Mengakibatkan instruksi kompilasi membaca memori unaligned; potensi crash (SIGBUS) pada ARM/MIPS; penurunan throughput memory access hingga 300%. | Hanya digunakan jika keterbatasan kapasitas storage/RAM absolut (Embedded <32KB SRAM). |
| **Fixed-Point vs IEEE Float** | Deterministik 100%; tidak ada rounding anomaly; kompatibel dengan ALU integer ultra cepat. | Dynamic range terbatas; potensi overflow eksponensial jika penskalaan salah; operasi kalkulasi non-linear (sqrt, sin) lambat. | FinTech, Core Ledger, Game Engine Physics Logic, Regulasi Finansial. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Signed Left Shift Memicu UB
*Salah:*
```c
int32_t mask = 1 << 31; // UB: Menggeser '1' ke posisi sign bit pada signed 32-bit integer!
```
*Benar:*
```c
uint32_t mask = 1U << 31; // Defined: Unsigned shift beroperasi modulo 2^32
```

#### 10.2 Type Punning Melanggar Strict Aliasing Rule
*Salah:*
```c
float f = 5.5f;
// Mengakses memori float melalui pointer uint32_t melanggar ISO C Strict Aliasing
uint32_t u = *(uint32_t*)&f; // UB! Optimizer dapat mengabaikan modifikasi pointer
```
*Benar:*
```c
float f = 5.5f;
uint32_t u;
memcpy(&u, &f, sizeof(u)); // Legal, dijamin aman oleh standar ISO C, dioptimalkan jadi no-op oleh compiler
```

#### 10.3 Perbandingan Langsung Floating Point Equality
*Salah:*
```c
double x = 0.1 * 3;
if (x == 0.3) { /* Seringkali gagal dieksekusi */ }
```
*Benar:*
```c
#include <math.h>
#define EPSILON 1e-9
double x = 0.1 * 3;
if (fabs(x - 0.3) < EPSILON) { /* Deterministik */ }
```

#### 10.4 Integer Promotion Mengorbankan Bit Inversion
*Salah:*
```c
uint8_t val = 0xAA;
// Operasi ~val mempromosikan val ke tipe signed int (0x000000AA -> 0xFFFFFF55)
// Pada sistem 32/64 bit, pergeseran selanjutnya membawa bit-bit hasil promosi
uint8_t inverted = ~val >> 4; // Hasil bukan 0x05 melainkan 0xF5!
```
*Benar:*
```c
uint8_t val = 0xAA;
uint8_t inverted = (uint8_t)(~val) >> 4; // Explicit masking/truncation
```

---

### 11. Best Practices & Production Checklist

- [ ] **Defensive Typing:** Wajib memakai `<stdint.h>`. Larang penggunaan `short`, `long`, `unsigned` tanpa penentu ukuran presisi pada API publik.
- [ ] **Compiler Sanitizers:** Wajib mengaktifkan runtime flag deteksi UB saat testing:
  ```bash
  -fsanitize=undefined -fsanitize=integer -fsanitize=bounds
  ```
- [ ] **Strict Compilation Flags:** Set compiler flag ke standar keamanan tinggi:
  ```bash
  -Wall -Wextra -Werror -Wconversion -Wsign-conversion -Wstrict-aliasing=2 -fno-common
  ```
- [ ] **Explicit Unsigned Literals:** Gunakan akhiran literal yang tepat: `U` untuk `uint32_t`, `ULL` untuk `uint64_t`.
- [ ] **Safe Bitwise Masking:** Pastikan nilai geser (*shift operand*) selalu divalidasi: $0 \le \text{shift} < \text{bit width}$.
- [ ] **Static Assertions:** Gunakan `static_assert` (C11 `_Static_assert`) untuk memvalidasi ukuran struct di compile-time:
  ```c
  _Static_assert(sizeof(TelemetryPayload) == 16, "Struct size alignment mismatch detected!");
  ```

---

### 12. Hands-on Practice: Membangun Sub-Sistem Parsing & Validasi Biner

Sistem ini akan dibangun pada direktori kerja: `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── Makefile
├── include/
│   ├── binary_safe.h
│   └── packet_def.h
└── src/
    ├── binary_safe.c
    ├── packet_parser.c
    └── main.c
```

#### File Implementation

##### `hands-on/m02/include/binary_safe.h`
```c
#ifndef BINARY_SAFE_H
#define BINARY_SAFE_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

uint16_t read_be16(const uint8_t *buffer);
uint32_t read_be32(const uint8_t *buffer);
uint64_t read_be64(const uint8_t *buffer);

void write_be16(uint8_t *buffer, uint16_t value);
void write_be32(uint8_t *buffer, uint32_t value);
void write_be64(uint8_t *buffer, uint64_t value);

bool safe_add_u64(uint64_t a, uint64_t b, uint64_t *result);
bool safe_mul_u64(uint64_t a, uint64_t b, uint64_t *result);

#endif // BINARY_SAFE_H
```

##### `hands-on/m02/src/binary_safe.c`
```c
#include "binary_safe.h"
#include <string.h>

uint16_t read_be16(const uint8_t *buffer) {
    return (uint16_t)((uint16_t)buffer[0] << 8 | (uint16_t)buffer[1]);
}

uint32_t read_be32(const uint8_t *buffer) {
    return ((uint32_t)buffer[0] << 24) |
           ((uint32_t)buffer[1] << 16) |
           ((uint32_t)buffer[2] << 8)  |
           ((uint32_t)buffer[3]);
}

uint64_t read_be64(const uint8_t *buffer) {
    return ((uint64_t)buffer[0] << 56) |
           ((uint64_t)buffer[1] << 48) |
           ((uint64_t)buffer[2] << 40) |
           ((uint64_t)buffer[3] << 32) |
           ((uint64_t)buffer[4] << 24) |
           ((uint64_t)buffer[5] << 16) |
           ((uint64_t)buffer[6] << 8)  |
           ((uint64_t)buffer[7]);
}

void write_be16(uint8_t *buffer, uint16_t value) {
    buffer[0] = (uint8_t)(value >> 8);
    buffer[1] = (uint8_t)(value);
}

void write_be32(uint8_t *buffer, uint32_t value) {
    buffer[0] = (uint8_t)(value >> 24);
    buffer[1] = (uint8_t)(value >> 16);
    buffer[2] = (uint8_t)(value >> 8);
    buffer[3] = (uint8_t)(value);
}

void write_be64(uint8_t *buffer, uint64_t value) {
    for (size_t i = 0; i < 8; ++i) {
        buffer[7 - i] = (uint8_t)(value >> (i * 8));
    }
}

bool safe_add_u64(uint64_t a, uint64_t b, uint64_t *result) {
    if (UINT64_MAX - a < b) {
        return false;
    }
    *result = a + b;
    return true;
}

bool safe_mul_u64(uint64_t a, uint64_t b, uint64_t *result) {
    if (a != 0 && b > UINT64_MAX / a) {
        return false;
    }
    *result = a * b;
    return true;
}
```

##### `hands-on/m02/include/packet_def.h`
```c
#ifndef PACKET_DEF_H
#define PACKET_DEF_H

#include <stdint.h>
#include <stdbool.h>

#define PACKET_MAGIC 0xCAFE
#define PACKET_MAX_PAYLOAD 1024

typedef struct {
    uint16_t magic;
    uint8_t  version;
    uint8_t  command;
    uint32_t sequence;
    uint32_t payload_len;
    uint32_t checksum;
} NetworkHeader;

_Static_assert(sizeof(NetworkHeader) == 16, "Header size mismatch!");

#endif // PACKET_DEF_H
```

##### `hands-on/m02/src/main.c`
```c
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include "binary_safe.h"
#include "packet_def.h"

static uint32_t compute_crc32_bitwise(const uint8_t *data, size_t length) {
    uint32_t crc = 0xFFFFFFFFU;
    for (size_t i = 0; i < length; ++i) {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; ++j) {
            crc = (crc >> 1) ^ (0xEDB88320U & (-(uint32_t)(crc & 1U)));
        }
    }
    return ~crc;
}

int main(void) {
    printf("[*] Starting Enterprise Binary Safe Subsystem Test...\n");

    uint8_t wire_buffer[16 + 4]; // 16-byte header + 4-byte payload
    
    // Construct Packet
    write_be16(wire_buffer + 0, PACKET_MAGIC);
    wire_buffer[2] = 0x01; // Version
    wire_buffer[3] = 0x0A; // Command
    write_be32(wire_buffer + 4, 10001); // Seq
    write_be32(wire_buffer + 8, 4);     // Payload length
    
    // Mock Payload
    wire_buffer[16] = 0xDE;
    wire_buffer[17] = 0xAD;
    wire_buffer[18] = 0xBE;
    wire_buffer[19] = 0xEF;

    // Checksum over payload
    uint32_t payload_crc = compute_crc32_bitwise(wire_buffer + 16, 4);
    write_be32(wire_buffer + 12, payload_crc);

    // Parsing Validation
    uint16_t parsed_magic = read_be16(wire_buffer);
    assert(parsed_magic == PACKET_MAGIC);
    
    uint32_t parsed_len = read_be32(wire_buffer + 8);
    assert(parsed_len == 4);

    uint32_t parsed_crc = read_be32(wire_buffer + 12);
    assert(parsed_crc == payload_crc);

    // Overflow Arithmetic Check
    uint64_t overflow_res;
    bool status = safe_add_u64(UINT64_MAX, 1U, &overflow_res);
    assert(status == false);

    printf("[+] All Bitwise & Binary Architecture Tests Passed Successfully!\n");
    return 0;
}
```

##### `hands-on/m02/Makefile`
```makefile
CC = gcc
CFLAGS = -Wall -Wextra -Werror -Wconversion -Wsign-conversion -O2 -Iinclude -fsanitize=undefined
SRC = src/binary_safe.c src/main.c
TARGET = hands_on_m02_bin

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) $(SRC) -o $(TARGET)

clean:
	rm -f $(TARGET)

run: all
	./$(TARGET)

.PHONY: all clean run
```

---

### 13. Exercise

#### Level: Easy
Implementasikan fungsi portabel pembalik urutan bit (bit-reversal) untuk tipe `uint8_t` (contoh: input biner `11010000` menjadi `00001011`). Larang penggunaan tipe data floating point.

*Kunci Solusi Ringkas:*
Gunakan kombinasi teknik swap nibble dan masking bit berurutan:
```c
uint8_t reverse_bits_u8(uint8_t b) {
    b = (uint8_t)((b & 0xF0) >> 4 | (b & 0x0F) << 4);
    b = (uint8_t)((b & 0xCC) >> 2 | (b & 0x33) << 2);
    b = (uint8_t)((b & 0xAA) >> 1 | (b & 0x55) << 1);
    return b;
}
```

#### Level: Medium
Tuliskan fungsi kalkulasi aritmetika saturasi penambahan 32-bit bertanda (*signed 32-bit saturating add*). Jika operasi menghasilkan nilai yang melampaui `INT32_MAX`, fungsi harus mengembalikan `INT32_MAX`. Jika bernilai di bawah `INT32_MIN`, fungsi harus mengembalikan `INT32_MIN`. Fungsi tidak boleh memicu Undefined Behavior pada signed integer underflow/overflow.

*Kunci Solusi Ringkas:*
```c
int32_t saturating_add_i32(int32_t a, int32_t b) {
    int32_t res;
    if (__builtin_add_overflow(a, b, &res)) {
        return (a > 0) ? INT32_MAX : INT32_MIN;
    }
    return res;
}
```

#### Level: Hard
Konversikan representasi floating-point single-precision IEEE 754 (32-bit) menjadi Brain Floating Point (`bfloat16` - 16 bit) secara manual murni menggunakan operasi bitwise, dengan menerapkan pembulatan deterministik *Round to Nearest Even* (bukan sekadar melakukan pemotongan bit/truncation).

*Kunci Solusi Ringkas:*
`bfloat16` menggunakan sign 1-bit, exponent 8-bit, dan mantissa 7-bit (mengambil 16 bit teratas dari `float32`).
```c
uint16_t float32_to_bfloat16_rne(float val) {
    uint32_t f_bits;
    memcpy(&f_bits, &val, sizeof(f_bits));

    // Handle NaN
    if ((f_bits & 0x7F800000U) == 0x7F800000U) {
        uint16_t res = (uint16_t)(f_bits >> 16);
        return (uint16_t)(res | 0x0040U); // Pastikan quiet NaN
    }

    uint32_t lsb = (f_bits >> 16) & 1U;
    uint32_t round_bias = 0x7FFFU + lsb; // Round to nearest even
    f_bits += round_bias;
    return (uint16_t)(f_bits >> 16);
}
```

---

### 14. Challenge: High-Frequency L2 Order Book Bit-Packed Delta Engine

**Skenario Misi Kritis:**
Anda adalah Systems Architect pada bursa derivatif kripto tier-1. Jaringan mengalami bottleneck throughput paket karena format JSON/Protobuf memakan bandwidth berlebih. Anda ditugaskan merancang format serialisasi L2 Order Book Delta kustom yang dipadatkan ke dalam ukuran **tepat 8 byte per update**, dengan spesifikasi field:
*   `Action`: 2-bit (0 = Add, 1 = Modify, 2 = Delete, 3 = Reserve)
*   `Side`: 1-bit (0 = Buy, 1 = Sell)
*   `Reserved`: 5-bit (Padding)
*   `Price Level Offset`: 24-bit unsigned integer (merepresentasikan unit basis harga hingga $167,772.15$)
*   `Quantity`: 32-bit unsigned integer

**Persyaratan:**
1.  Implementasikan serializer dan deserializer C yang mengompresi struktur data tersebut ke dalam array biner `uint8_t buffer[8]`.
2.  Desain implementasi Anda agar **100% bebas dari Endianness Traps** (dapat di-serialize pada CPU Little-Endian x86_64 dan di-deserialize secara tepat pada CPU Big-Endian tanpa distorsi bit).
3.  Implementasikan validasi batas (*bounds check*) tanpa percabangan if-else (*branchless*) untuk performa decoding tingkat kernel.
4.  Larang penggunaan bit-fields compiler C standar.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Berapakah representasi heksadesimal dari nilai bertanda `-5` pada arsitektur integer 8-bit Two's Complement?**
   * *Jawaban:* `0xFB`. (Formula: $256 - 5 = 251 = \text{0xFB}$).
2. **Mengapa ekspresi `(1 << 31)` memicu Undefined Behavior pada arsitektur dengan lebar default `int` 32-bit?**
   * *Jawaban:* Karena literal `1` bertipe `signed int`. Menggeser 1 ke bit ke-31 mengeksekusi signed bit overflow, yang merupakan Undefined Behavior menurut spesifikasi ISO C. Harus ditulis sebagai `(1U << 31)`.
3. **Apa perbedaan struktural utama antara representasi floating point `+0.0` dan `-0.0` pada standar IEEE 754?**
   * *Jawaban:* Sign bit pada `-0.0` bernilai 1, sedangkan pada `+0.0` bernilai 0. Exponent dan mantissa dari kedua nilai tersebut bernilai bit 0 seluruhnya.
4. **Pada arsitektur 64-bit, berapakah `sizeof` dari struct yang memiliki urutan anggota: `char a; double b; char c;`?**
   * *Jawaban:* 24 byte. Alasan: `a` (1 byte) + 7 byte padding; `b` (8 byte aligned); `c` (1 byte) + 7 byte tail padding (untuk alignment array berindeks berikutnya).
5. **Konversi urutan byte manakah yang dijalankan oleh instruksi fungsi standar `htonl`?**
   * *Jawaban:* Host Byte Order ke Network Byte Order (Little-Endian/Host menuju Big-Endian).

#### Intermediate (5 Pertanyaan)
1. **Mengapa type punning menggunakan teknik pointer cast `*(uint32_t*)&my_float` dapat merusak kode pada level optimasi `-O2/-O3`?**
   * *Jawaban:* Karena melanggar *C Strict Aliasing Rule*. Compiler berasumsi pointer dari tipe berbeda tidak akan mereferensikan lokasi memori fisik yang sama, sehingga optimizer dapat melakukan reordering atau mengabaikan instruksi write/read tersebut dari register.
2. **Apa yang terjadi ketika CPU mencoba melakukan eksekusi instruksi pembagian: `INT_MIN / -1` pada tipe signed 32-bit?**
   * *Jawaban:* Memicu Floating Point Exception / Hardware Divide Error Trap (SIGFPE) pada arsitektur x86_64. Hal ini dikarenakan hasil pembagian ($2^{31}$) melampaui kapasitas maksimum `INT32_MAX` ($2^{31}-1$).
3. **Mengapa penambahan angka floating point tidak bersifat asosiatif: `(a + b) + c != a + (b + c)`?**
   * *Jawaban:* Karena adanya penyesuaian eksponen dan pembulatan fraksi mantissa pada setiap langkah penambahan intermediate. Informasi mantissa pada magnitudo yang lebih kecil dapat tergeser keluar (hilang) sebelum ditambahkan dengan magnitudo yang besar.
4. **Jelaskan perbedaan mendasar perilaku pergeseran bit kanan (*right shift*) `>>` pada signed integer vs unsigned integer!**
   * *Jawaban:* Unsigned integer menggunakan *Logical Shift* (menyisipkan bit 0 pada MSB). Signed integer mengimplementasikan *Arithmetic Shift* (menyalin nilai sign bit lama ke posisi MSB baru untuk menjaga tanda aljabar).
5. **Kapan *subnormal numbers* pada floating point terbentuk, dan apa dampaknya terhadap performa latency mikroarsitektur CPU?**
   * *Jawaban:* Terbentuk ketika nilai eksponen bernilai `0` namun fraksi mantissa tidak bernilai nol (angka mendekati nol absolut). Dampaknya memicu latency parah (bisa memakan ratusan siklus CPU) karena sering kali memerlukan emulasi software microcode trap pada FPU.

#### Skenario Kasus Produksi (3 Pertanyaan)
1. **Kasus 1: Sinyal Abort Telemetri Ruang Angkasa.**
   Sebuah sistem avionik membaca sensor sudut menggunakan representasi 16-bit:
   ```c
   int16_t raw_gyro = read_bus();
   int32_t calibrated = raw_gyro * 1000 / 32;
   ```
   Sistem crash secara berkala akibat core dump ketika `raw_gyro` bernilai di bawah `-33`. Analisis akar masalahnya!
   * *Jawaban/Analisis:*
     Pada arsitektur 16-bit target MCU, `raw_gyro * 1000` dievaluasi dalam tipe `int` 16-bit. Untuk nilai `-33 * 1000 = -33000`, nilainya melampaui `INT16_MIN` ($-32768$). Terjadi *signed integer overflow* (UB) yang pada mikroarsitektur bersangkutan memicu hardware trap. Solusi: Lakukan *explicit casting* sebelum perkalian: `((int32_t)raw_gyro * 1000) / 32`.

2. **Kasus 2: Korupsi Data Jaringan Lintas-Arsitektur.**
   Sebuah payload biner dikirim dari server AMD64 (Little-Endian) ke mainframe s390x (Big-Endian). Payload didefinisikan sebagai:
   ```c
   struct Packet {
       uint32_t id;
       uint8_t payload[4];
   };
   ```
   Setelah deserialisasi langsung via copy memory, didapatkan bahwa `id` tertukar urutan bytenya, namun `payload` tetap terbaca benar. Mengapa elemen array byte tidak terpengaruh oleh Endianness?
   * *Jawaban/Analisis:*
     Endianness adalah aturan penataan byte untuk tipe data diskrit multi-byte (integer, float, pointer) di dalam memori. Array of `uint8_t` adalah kumpulan unit byte individual (masing-masing 1 byte) yang dialokasikan pada indeks alamat sekuensial ($+0, +1, +2, +3$), sehingga urutan indeks byte array selalu invarian terhadap arsitektur endianness hardware.

3. **Kasus 3: Kegagalan Compiler Optimization pada Masking.**
   Software engineer menuliskan rutin enkripsi:
   ```c
   void crypt_block(uint32_t *block, size_t count) {
       for(size_t i = 0; i < count; ++i) {
           block[i] = (block[i] << 8) | (block[i] >> 24);
       }
   }
   ```
   Rutin ini bekerja lambat saat profiling. Mengapa kode ini tidak menghasilkan instruksi single-cycle CPU `ROL` / `ROR`, dan bagaimana memperbaikinya?
   * *Jawaban/Analisis:*
     Operasi `(block[i] << 8) | (block[i] >> 24)` sering kali gagal dioptimasi oleh compiler lama jika tipe datanya mengalami *implicit integer promotion* atau optimasi idiom recognizer tidak aktif. Penggunaan builtin macro atau circular shift idiom modern:
     `#include <immintrin.h>` atau GCC standard builtin: `__builtin_rotateleft32(block[i], 8)` atau pattern masking canonical akan langsung diterjemahkan menjadi 1 instruksi mesin: `roll $8, %eax`.

---

### 16. Summary
Representasi bit dan penanganan tipe data primitif dalam bahasa C menuntut pemahaman konkret terhadap arsitektur perangkat keras:
1.  **Arsitektur Biner:** Representasi integer modern adalah Two's Complement. Operasi yang melampaui batas signed integer bukan sekadar menghasilkan wrap-around, melainkan memicu *Undefined Behavior* yang dapat dieksploitasi oleh optimizer compiler secara agresif.
2.  **IEEE 754 Floating-Point:** Presisi floating-point memiliki limitasi presisi struktural dan status ekstrim ($NaN$, $Inf$, Subnormal). Domain yang membutuhkan determinisme absolut (misalnya perbankan dan kripto) wajib menggunakan representasi integer terukur (*Fixed-Point Arithmetic*).
3.  **Memori & Alignment:** Akses memori hardware beroperasi pada batas kata biner (*bus boundaries*). Struct packing tanpa alignment yang tepat dapat melipatgandakan siklus akses memori atau menghasilkan hardware fault trap (`SIGBUS`).
4.  **Standar Produksi:** Rekayasa sistem level enterprise wajib memanfaatkan pustaka `<stdint.h>`, melakukan deserialisasi biner melalui `memcpy` untuk menjamin kepatuhan *Strict Aliasing*, serta menjalankan verifikasi kompilasi menggunakan runtime sanitizers (`-fsanitize=undefined,integer`).