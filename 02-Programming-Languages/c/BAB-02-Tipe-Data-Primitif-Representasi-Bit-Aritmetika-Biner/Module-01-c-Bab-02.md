# MODUL 02 — BAB 01: TIPE DATA PRIMITIF, REPRESENTASI BIT, & ARITMETIKA BINER

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** C-DEV-0201
* **Nama Modul:** Tipe Data Primitif, Representasi Bit, & Aritmetika Biner
* **Kategori:** 02-Programming-Languages / C
* **Tingkat Kesulitan:** Intermediate
* **Prasyarat:** Pemahaman dasar kompilasi C (GCC/Clang), alur kontrol (`if`, `for`, `while`), deklarasi variabel dasar, dan pengantar memori pointer.
* **Target Standar C:** ISO/IEC 9899:1999 (C99) & ISO/IEC 9899:2011 (C11)
* **Waktu Estimasi:** 4 - 6 Jam Pembelajaran Mandiri / Praktikum Terpandu

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis** representasi biner internal dari *signed* dan *unsigned integer* menggunakan sistem komplemen dua (*Two's Complement*).
2. **Mengurai** struktur internal bilangan floating-point standar IEEE 754 (Single Precision dan Double Precision) hingga ke level bit (*sign, exponent, mantissa*).
3. **Mendeteksi dan Menangani** *Integer Overflow*, *Underflow*, dan *Implicit Promotion* guna menghindari *Undefined Behavior* (UB).
4. **Mengimplementasikan** manipulasi bit tingkat rendah (*bitwise operations*: AND, OR, XOR, NOT, shift left/right) secara idiomatis dan deterministik.
5. **Mengelola** masalah portabilitas representasi memori lintas arsitektur hardware (*Endianness*: Little-Endian vs Big-Endian).
6. **Membangun** encoder/decoder biner berbasis *bit-level masking* dan serialisasi protokol jaringan yang aman tanpa ketergantungan *padding* struktural compiler.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Menembus Abstraksi Tingkat Tinggi
Dalam bahasa pemrograman tingkat tinggi (seperti Python atau JavaScript), tipe data seperti `number` atau `int` dipandang sebagai entitas matematika ideal yang memiliki kapasitas arbitrer atau perilaku otomatis. 

Dalam bahasa C, **abstraksi tersebut tidak ada**. 

```
Mental Model: "Everything in RAM is just an untyped sequence of electrical charges (bits)."
```

Bahasa C tidak melihat "angka 5" atau "huruf 'A'". Bahasa C melihat memori sebagai **deretan sel byte berurutan**. Tipe data hanyalah **lensa semantik** (*compiler instruction template*) yang menentukan:
1. Berapa banyak byte yang dialokasikan (lebar bit).
2. Bagaimana instruksi CPU (ALU) harus memperlakukan pola bit tersebut saat membaca, menulis, atau mengoperasikannya (signed integer, unsigned integer, IEEE 754 float, atau memory address).

Jika Anda salah memilih lensa (misalnya: salah melakukan *type casting* atau mengabaikan *sign extension*), CPU tidak akan memprotes; ia akan mengeksekusi operasi aritmetika pada pola bit tersebut secara harfiah, menghasilkan korupsi data senyap (*silent data corruption*) atau celah keamanan kritis (*exploitable security vulnerability*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Representasi Integer: Signed vs Unsigned (8-bit)

```
Bit Index:     7    6    5    4    3    2    1    0
Value Vector: 2^7  2^6  2^5  2^4  2^3  2^2  2^1  2^0
Unsigned:     128   64   32   16    8    4    2    1   -> Rentang: 0 .. 255

Signed (Two's Complement):
Bit Index:    -2^7  2^6  2^5  2^4  2^3  2^2  2^1  2^0
Value Vector: -128  64   32   16    8    4    2    1   -> Rentang: -128 .. 127
MSB (Bit 7) bertindak sebagai bobot negatif (-128).
```

### 2. Mekanisme Negasi Komplemen Dua (Two's Complement)

```
Nilai Awal (+5):           0 0 0 0 0 1 0 1
                           │ │ │ │ │ │ │ │
Langkah 1: Bitwise Invert (~5) [Komplemen Satu]
                           ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼
                           1 1 1 1 1 0 1 0
Langkah 2: Tambah 1 (+1)
                         +               1
                           ─────────────────
Hasil (-5):                1 1 1 1 1 0 1 1  (-128 + 64 + 32 + 16 + 8 + 0 + 2 + 1 = -5)
```

### 3. Layout IEEE 754 Single Precision Floating-Point (32-bit `float`)

```
 31 30        23 22                                 0
┌──┬────────────┬────────────────────────────────────┐
│S │  Exponent  │              Mantissa              │
│  │   (8 bit)  │              (23 bit)              │
└──┴────────────┴────────────────────────────────────┘
 1   <-- 8 bit -> <------------- 23 bit ------------->

Rumus: Value = (-1)^S * (1.Mantissa) * 2^(Exponent - 127)
```

### 4. Endianness Memory Mapping (Nilai 32-bit: `0xA1B2C3D4`)

```
Alamat Memori:      0x1000    0x1001    0x1002    0x1003
                   ┌─────────┬─────────┬─────────┬─────────┐
Big-Endian (MSB):  │  0xA1   │  0xB2   │  0xC3   │  0xD4   │ (Network Byte Order)
                   └─────────┴─────────┴─────────┴─────────┘
Little-Endian(LSB):│  0xD4   │  0xC3   │  0xB2   │  0xA1   │ (x86_64, ARM default)
                   └─────────┴─────────┴─────────┴─────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Status Register ALU dan Hardware Flags
Ketika mikroprosesor (x86 atau ARM) mengeksekusi operasi aritmetika melalui Arithmetic Logic Unit (ALU), operasi tersebut mempengaruhi sekumpulan *flag* pada register status CPU (misalnya `EFLAGS` pada x86):

1. **CF (Carry Flag):** Diset jika terjadi *overflow* pada operasi aritmetika *unsigned* (ada bit sisa yang keluar dari kapasitas register).
2. **OF (Overflow Flag):** Diset jika terjadi *overflow* pada operasi aritmetika *signed* (misalnya penambahan dua bilangan positif menghasilkan bit tanda negatif).
3. **ZF (Zero Flag):** Diset jika hasil operasi bernilai tepat 0.
4. **SF (Sign Flag):** Diset sama dengan Most Significant Bit (MSB) dari hasil operasi.

### Signed vs Unsigned di Level Mesin
Di tingkat assembly, instruksi penambahan (`ADD`) untuk *signed* dan *unsigned* adalah sama persis. ALU hanya menjumlahkan bit-bit biner. Interpretasi apakah hasil tersebut meluap (*overflow*) diserahkan kepada software melalui pembacaan flag yang berbeda:
* Program membaca **CF** untuk memvalidasi batasan *unsigned*.
* Program membaca **OF** untuk memvalidasi batasan *signed*.

Namun, standar C menetapkan aturan fundamental:
* **Unsigned Integer Overflow:** Terdefinisi dengan baik (*well-defined behavior*). Nilainya berputar secara modular: $\text{result} = \text{computed} \pmod{2^N}$.
* **Signed Integer Overflow:** Bersifat **Undefined Behavior (UB)**. Compiler C modern (seperti GCC dengan optimasi `-O2` atau `-O3`) berhak mengasumsikan bahwa *signed integer overflow* tidak pernah terjadi, dan dapat mengeliminasi logika pemeriksaan keamanan Anda jika ditulis secara keliru.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Lebar Primitif dan Portabilitas (`stdint.h`)
Dalam standar C klasik (C89), ukuran `short`, `int`, `long`, dan `long long` tidak memiliki ukuran pasti, melainkan hanya batas minimum:
* `short` $\ge 16$ bit
* `int` $\ge 16$ bit (umumnya 32 bit pada arsitektur modern)
* `long` $\ge 32$ bit (pada Linux x86_64 berukuran 64 bit, sedangkan pada Windows x86_64 berukuran 32 bit [model LLP64 vs LP64])
* `long long` $\ge 64$ bit

Untuk rekayasa perangkat lunak modern dan sistem berkeandalan tinggi, gunakan tipe tetap (*exact-width integer types*) dari `<stdint.h>`:
* `uint8_t`, `int8_t`: Tepat 8 bit.
* `uint16_t`, `int16_t`: Tepat 16 bit.
* `uint32_t`, `int32_t`: Tepat 32 bit.
* `uint64_t`, `int64_t`: Tepat 64 bit.
* `size_t`: Tipe unsigned untuk merepresentasikan ukuran objek dalam memori (32 bit pada OS 32-bit, 64 bit pada OS 64-bit).
* `uintptr_t`: Tipe integer unsigned yang dijamin mampu menampung alamat pointer tanpa pemotongan data (*truncation*).

### 2. Aturan Integer Promotion dan Usual Arithmetic Conversions
Sebelum operasi aritmetika dieksekusi oleh ALU, tipe integer yang memiliki *rank* lebih rendah dari `int` (seperti `char`, `short`, `bool`, baik signed maupun unsigned) akan mengalami **Integer Promotion** menjadi `int` (atau `unsigned int` jika `int` tidak dapat menampung rentang nilai aslinya).

```c
uint8_t a = 200;
uint8_t b = 100;
// a dan b dipromosikan ke 'int' sebelum dijumlahkan
// Hasil 300 muat dalam 'int' bertipe 32-bit
// Kemudian hasil 300 ditruncate saat dikembalikan ke uint8_t -> 300 % 256 = 44
uint8_t c = a + b; 
```

Masalah berbahaya muncul pada perbandingan antara tipe signed dan unsigned:
```c
int32_t x = -1;
uint32_t y = 1;
if (x < y) {
    // BLOK INI TIDAK AKAN DIEKSEKUSI!
} else {
    // BLOK INI AKAN DIEKSEKUSI!
}
```
**Mengapa?** Berdasarkan aturan *Usual Arithmetic Conversions*, jika salah satu operand bertipe `unsigned int` dan operand lainnya bertipe `signed int` dengan ukuran yang sama, operand bertipe `signed` akan di-*cast* secara implisit ke `unsigned`. Nilai `-1` dalam bentuk biner 32-bit komplemen dua adalah `0xFFFFFFFF`, yang jika dibaca sebagai `uint32_t` bernilai `4.294.967.295`. Akibatnya, `4294967295 < 1` bernilai salah (*false*).

### 3. Operasi Bitwise: Arithmetic Shift vs Logical Shift
* **Logical Shift Right (`>>` pada tipe unsigned):** Bit kosong di sebelah kiri selalu diisi dengan `0`.
* **Arithmetic Shift Right (`>>` pada tipe signed):** Menggandakan *sign bit* (MSB) ke bit-bit baru yang masuk di sebelah kiri untuk mempertahankan tanda bilangan.

> **Peringatan Standar C:** Menggeser bilangan bertipe *signed* yang bernilai negatif adalah **Implementation-Defined Behavior**. Menggeser nilai dengan jumlah bit $\ge$ ukuran lebar tipe data (misal: `x << 32` pada integer 32-bit) atau menggeser nilai negatif adalah **Undefined Behavior**.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL (STEP-BY-STEP)

Program berikut mendemonstrasikan inspeksi langsung representasi biner memori untuk tipe integer dan floating-point tanpa melanggar aturan *Strict Aliasing*.

```c
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

/**
 * Mencetak representasi biner dari buffer memori arbitrer secara byte per byte.
 */
void print_raw_memory_bits(const void *ptr, size_t size) {
    const uint8_t *bytes = (const uint8_t *)ptr;
    
    // Iterasi dari byte dengan alamat tertinggi ke terendah (Big-Endian visual ordering)
    for (size_t i = size; i > 0; --i) {
        uint8_t current_byte = bytes[i - 1];
        for (int8_t bit = 7; bit >= 0; --bit) {
            putchar((current_byte & (1U << bit)) ? '1' : '0');
        }
        putchar(' ');
    }
    putchar('\n');
}

/**
 * Demonstrasi inspeksi komponen internal IEEE 754 Single Precision
 */
void inspect_float_ieee754(float val) {
    uint32_t raw_bits;
    // Menggunakan memcpy untuk menghindari Undefined Behavior dari type-punning via pointer
    memcpy(&raw_bits, &val, sizeof(raw_bits));

    uint32_t sign = (raw_bits >> 31) & 0x01;
    uint32_t exponent = (raw_bits >> 23) & 0xFF;
    uint32_t mantissa = raw_bits & 0x7FFFFF;

    printf("Nilai Float: %f\n", val);
    printf("Raw Hex    : 0x%08X\n", raw_bits);
    printf("Sign Bit   : %u (%s)\n", sign, sign ? "Negatif" : "Positif");
    printf("Exponent   : %u (Unbiased: %d)\n", exponent, (int)exponent - 127);
    printf("Mantissa   : 0x%06X (Frac binary fraction)\n", mantissa);
    printf("Binary Map : ");
    print_raw_memory_bits(&val, sizeof(val));
    printf("--------------------------------------------------\n");
}

int main(void) {
    printf("=== INSPEKSI MEMORI: TWO'S COMPLEMENT ===\n");
    int8_t pos_val = 5;
    int8_t neg_val = -5;
    
    printf("Representasi +5 (int8_t) : ");
    print_raw_memory_bits(&pos_val, sizeof(pos_val));

    printf("Representasi -5 (int8_t) : ");
    print_raw_memory_bits(&neg_val, sizeof(neg_val));

    printf("\n=== PEMBUKTIAN IMPLICIT PROMOTION TRAP ===\n");
    int32_t a = -1;
    uint32_t b = 1;
    printf("Perbandingan: (int32_t)-1 < (uint32_t)1\n");
    if (a < b) {
        printf("Hasil: TRUE (Sesuai logika matematika)\n");
    } else {
        printf("Hasil: FALSE (Terjadi Implicit Conversion ke unsigned!)\n");
        printf("Raw Hex (uint32_t) dari -1: 0x%08X\n", (uint32_t)a);
    }

    printf("\n=== INSPEKSI MEMORI: FLOATING POINT IEEE 754 ===\n");
    inspect_float_ieee754(12.375f);
    inspect_float_ieee754(-0.0f);
    
    return 0;
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis dari program di atas:

1. **Baris 11 (`const uint8_t *bytes = (const uint8_t *)ptr;`):**
   Standar C secara eksplisit memperbolehkan tipe `char *` atau `uint8_t *` (karakter bertanda/tak bertanda) melakukan aliasing terhadap pointer tipe apa pun untuk membaca representasi mentah byte (*byte-level aliasing rule*).
2. **Baris 14–19 (Looping cetak bit):**
   `1U << bit` membuat *mask* biner (misal jika bit = 3, maka `00001000`). Operasi `current_byte & (1U << bit)` mengekstrak bit tertentu. Tanda ternary memilih karakter `'1'` atau `'0'`.
3. **Baris 27 (`memcpy(&raw_bits, &val, sizeof(raw_bits));`):**
   Melakukan penyalinan bit mentah dari variabel `float` ke `uint32_t`. Pendekatan ini aman dan bebas dari pelanggaran *Strict Aliasing Rule* (berbeda jika melakukan `*(uint32_t*)&val` yang merupakan Undefined Behavior dalam C99).
4. **Baris 29–31 (Bit masking IEEE 754):**
   * `(raw_bits >> 31) & 0x01`: Menggeser bit tanda dari posisi ke-31 ke posisi terendah dan memfilternya.
   * `(raw_bits >> 23) & 0xFF`: Menggeser bidang eksponen sejauh 23 bit ke kanan, lalu menerapkan mask `0xFF` (8 bit).
   * `raw_bits & 0x7FFFFF`: Mengisolasi 23 bit mantissa/significand paling kanan (`0x7FFFFF` = 23 bit satu).
5. **Baris 51–57 (Implicit Promotion Trap):**
   Operasi perbandingan `a < b` memicu penaikan tipe signed integer `a` (-1) menjadi `unsigned int`. Bitwise `-1` tetap `0xFFFFFFFF`, namun interpretasi nilainya melonjak menjadi `4,294,967,295`, membalikkan hasil logika evaluasi.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Konteks: Gateway Protokol Sensor IoT Industri
Dalam arsitektur *Industrial Internet of Things* (IIoT), ribuan mikrokontroler (Edge Nodes berbasis arsitektur Little-Endian ARM Cortex-M) mengirimkan telemetri lingkungan ke Server Gateway (x86_64) melalui kanal bandwidth sempit (misalnya NB-IoT atau LoRaWAN).

Untuk menghemat konsumsi energi modul radio dan bandwidth, data dilarang dikirimkan dalam format teks (JSON/XML). Protokol transfer mewajibkan **Binary Frame Encoding** padat dengan spesifikasi berikut:

```
PANJANG TOTAL PAKET: 8 BYTE
Byte 0       : Sync Byte (Harus selalu 0xAA)
Byte 1       : Bitfields Flag:
               - Bit [7]   : Sensor Fault Warning (1 bit)
               - Bit [6..4]: Operating Mode (3 bit: Normal=0, Eco=1, Boost=2, Calib=3)
               - Bit [3..0]: Node Protocol Version (4 bit: rentang 0-15)
Byte 2-3     : Raw Temperature (16-bit Signed Integer, Skala: Celcius * 100, Network Byte Order / Big-Endian)
Byte 4-5     : Raw Humidity (16-bit Unsigned Integer, Skala: % * 100, Network Byte Order / Big-Endian)
Byte 6-7     : CRC-16-CCITT Checksum (Perhitungan atas Byte 0 sampai 5)
```

Tantangan utama yang sering memicu kegagalan sistem pada implementasi ini adalah:
1. Perbedaan *endianness* (Sensor ARM Little-Endian mengirimkan data secara Big-Endian sesuai standar transmisi jaringan).
2. Kesalahan penanganan data temperatur negatif saat dikonversi dari 16-bit *signed* ke representasi *floating-point*.
3. Kerentanan struktur (*struct padding*) jika parser memetakan buffer memori mentah langsung ke deklarasi `struct` C.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi parser biner telemetri tingkat produksi yang portabel, deterministik, aman dari serangan *buffer overrun*, dan kebal terhadap *endianness mismatch*.

```c
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#define PACKET_SYNC_BYTE        0xAA
#define PACKET_FRAME_SIZE       8
#define CRC16_POLYNOMIAL        0x1021

typedef struct {
    bool     fault_warning;
    uint8_t  operating_mode;
    uint8_t  protocol_version;
    float    temperature_c;
    float    humidity_pct;
} TelemetryData;

/**
 * Menghitung CRC16-CCITT (False) secara bitwise deterministik.
 */
static uint16_t calculate_crc16(const uint8_t *data, size_t length) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; ++i) {
        crc ^= ((uint16_t)data[i] << 8);
        for (uint8_t bit = 0; bit < 8; ++bit) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ CRC16_POLYNOMIAL;
            } else {
                crc = (crc << 1);
            }
        }
    }
    return crc;
}

/**
 * Melakukan parsing frame biner telemetri secara aman.
 * Menghindari struct memory casting guna mencegah padding issues & undefined behavior.
 */
bool parse_telemetry_packet(const uint8_t *stream_buffer, size_t buffer_len, TelemetryData *out_data) {
    if (stream_buffer == NULL || out_data == NULL) {
        return false;
    }

    if (buffer_len < PACKET_FRAME_SIZE) {
        return false; // Buffer underrun
    }

    // 1. Verifikasi Header Sync Byte
    if (stream_buffer[0] != PACKET_SYNC_BYTE) {
        return false; // Desinkronisasi protokol
    }

    // 2. Verifikasi Integritas Data via Checksum (CRC-16)
    uint16_t packet_crc = ((uint16_t)stream_buffer[6] << 8) | (uint16_t)stream_buffer[7];
    uint16_t computed_crc = calculate_crc16(stream_buffer, 6);
    
    if (packet_crc != computed_crc) {
        return false; // Data corrupt / bit flip
    }

    // 3. Dekonstruksi Bitfield Flag (Byte 1)
    uint8_t flags_byte = stream_buffer[1];
    out_data->fault_warning    = (flags_byte >> 7) & 0x01;
    out_data->operating_mode   = (flags_byte >> 4) & 0x07; // Mask 3-bit: 0b111 = 0x07
    out_data->protocol_version = flags_byte & 0x0F;        // Mask 4-bit: 0b1111 = 0x0F

    // 4. Rekonstruksi Temperature (Signed 16-bit Big-Endian)
    // Hindari undefined behavior sign extension dengan parsing ke unsigned terlebih dahulu
    uint16_t raw_temp_be = ((uint16_t)stream_buffer[2] << 8) | (uint16_t)stream_buffer[3];
    int16_t raw_temp_signed;
    // Explicitly copy ke signed int16_t untuk memetakan komplemen dua
    memcpy(&raw_temp_signed, &raw_temp_be, sizeof(raw_temp_signed));
    out_data->temperature_c = (float)raw_temp_signed / 100.0f;

    // 5. Rekonstruksi Humidity (Unsigned 16-bit Big-Endian)
    uint16_t raw_hum_be = ((uint16_t)stream_buffer[4] << 8) | (uint16_t)stream_buffer[5];
    out_data->humidity_pct = (float)raw_hum_be / 100.0f;

    return true;
}

int main(void) {
    // Simulasi Paket Transmisi Masuk dari Jaringan:
    // Sync: 0xAA
    // Flags: 0xA2 -> Binary: 1 010 0010 (Fault: 1, Mode: 2 [Boost], Ver: 2)
    // Raw Temp: 0xFE 0x0C -> Nilai signed -500 (desimal) -> -5.00 Celcius
    // Raw Hum:  0x1D 0x4C -> Nilai unsigned 7500 (desimal) -> 75.00 %
    // CRC-16 dihitung manual/komputer untuk payload di atas: 0x937B
    uint8_t mock_network_frame[PACKET_FRAME_SIZE] = {
        0xAA, 
        0xA2, 
        0xFE, 0x0C, 
        0x1D, 0x4C, 
        0x93, 0x7B
    };

    TelemetryData current_metrics;
    
    printf("Mencoba parsing frame biner (%d byte)...\n", PACKET_FRAME_SIZE);
    if (parse_telemetry_packet(mock_network_frame, sizeof(mock_network_frame), &current_metrics)) {
        printf("[SUCCESS] Telemetri Terbaca Valid:\n");
        printf(" - Protocol Version : %u\n", current_metrics.protocol_version);
        printf(" - Operating Mode    : %u\n", current_metrics.operating_mode);
        printf(" - Fault Status      : %s\n", current_metrics.fault_warning ? "ACTIVE FAULT" : "NORMAL");
        printf(" - Temperature       : %.2f degC\n", current_metrics.temperature_c);
        printf(" - Humidity          : %.2f %%\n", current_metrics.humidity_pct);
    } else {
        printf("[ERROR] Paket tidak valid (Sync mismatch / CRC Error / Truncated).\n");
    }

    return 0;
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Pendekatan Deserialisasi: Struct Overlay vs Explicit Bit Shifting

| Kriteria | Direct Struct Overlay (`(Packet*)buf`) | Explicit Bit Shifting (`<<`, `>>`, `&`) |
| :--- | :--- | :--- |
| **Kinerja Eksekusi** | Sangat cepat ($O(1)$, instruksi baca memori tunggal). | Sangat cepat ($O(1)$, beberapa operasi register CPU). |
| **Kompatibilitas Endianness**| **Gagal Lintas Arsitektur** (Bergantung pada host endianness). | **Universal** (Berfungsi identik di Big/Little Endian). |
| **Struct Memory Alignment**| Rawan bug; Compiler menyisipkan *padding bytes* tak terduga. | Kebal dari efek *structure padding*. |
| **Keamanan Memori** | Risiko crash akibat *Unaligned Memory Access* pada CPU tertentu. | 100% aman (Akses memori berbasis byte selalu *aligned*). |
| **Portabilitas Kode** | Bergantung pada ekstensi compiler non-standar (`#pragma pack`).| Ditentukan secara ketat oleh standar murni ISO C. |

### Tipikal Pemilihan Tipe Numerik

* **`float` vs `double`:** Gunakan `float` untuk lingkungan dengan keterbatasan memori ketat (embedded) atau pemrosesan GPU/SIMD vektor masif. Gunakan `double` sebagai default komputasi saintifik presisi untuk memitigasi akumulasi *rounding error*.
* **`fixed-point` vs `floating-point`:** Pada mikrokontroler tanpa unit FPU (*Floating Point Unit* berbasis hardware), emulasi perangkat lunak untuk floating-point sangat lambat. Gunakan aritmetika bilangan bulat skala tetap (*fixed-point arithmetic*, seperti penskalaan `* 100` pada studi kasus di atas).

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Asymmetric Range of Two's Complement
Rentang nilai integer bertanda 8-bit adalah `-128` sampai `+127`. 
Perhatikan anomali saat mencoba melakukan negasi pada batas bawah:

```c
int8_t x = -128;
int8_t y = -x; // OVERFLOW! 
```
Nilai `+128` **tidak dapat direpresentasikan** dalam `int8_t`. Mengasumsikan bahwa `-x` selalu bernilai positif adalah kesalahan logika kritis. Pada tipe data `int` standar, mengeksekusi `-INT_MIN` memicu **Signed Integer Overflow (Undefined Behavior)**.

### 2. Shift Count Exceeding Width
```c
uint32_t val = 1U;
uint32_t broken = val << 32; // UNDEFINED BEHAVIOR
```
Berdasarkan ISO C standar, menggeser nilai dengan jumlah bit yang sama atau lebih besar dari lebar tipe data operand kiri adalah Undefined Behavior. Di mikroprosesor Intel x86, instruksi assembler `SHL` menerapkan modulasi mask `32 & 0x1F = 0`, sehingga `val << 32` justru menghasilkan `val << 0` (nilai tidak berubah), bukan `0`.

### 3. Representasi Floating-Point "NaN" dan Negatif Nol
* Floating-point memiliki dua nilai nol: `+0.0f` dan `-0.0f`. Keduanya bernilai sama jika dibandingkan dengan operator `==`, tetapi memiliki representasi biner berbeda (bit tanda berbeda).
* Nilai `NaN` (*Not a Number*) memiliki karakteristik unik: ekspresi `(NaN == NaN)` selalu bernilai **FALSE**. Evaluasi nilai float tidak boleh menggunakan operator kesetaraan langsung `==`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Kesalahan Sign Extension pada Casting Byte
**Kode Bermasalah:**
```c
char byte = 0x80;
int32_t expanded = byte; // expanded bernilai 0xFFFFFF80 (-128), BUKAN 0x00000080 (128)
```
**Mengapa Terjadi:** Pada sebagian besar sistem, tipe `char` default-nya adalah `signed`. Saat dipromosikan ke ukuran 32-bit, CPU melakukan *Sign Extension* (mengisi bit-bit kosong kiri dengan nilai MSB yaitu 1).
**Solusi Defensif:**
```c
uint8_t byte = 0x80;
int32_t expanded = (uint32_t)byte; // Nilai aman: 0x00000080
```

### 2. Kesalahan Prioritas Operator Bitwise
**Kode Bermasalah:**
```c
if (status & 0x01 == 0) // BUG! Dievaluasi sebagai: status & (0x01 == 0) -> status & 0
```
**Mengapa Terjadi:** Dalam hirarki operator C, operator kesetaraan (`==`, `!=`) memiliki presedensi lebih tinggi dibandingkan operator bitwise (`&`, `|`, `^`).
**Solusi Defensif:** Selalu gunakan tanda kurung secara eksplisit:
```c
if ((status & 0x01) == 0)
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Literal Unsigned secara Eksplisit:** Saat melakukan manipulasi bit, selalu tambahkan sufiks `U` atau `UL` pada literal numerik untuk mencegah promosi implisit bertanda yang membahayakan.
   * *Contoh:* Gunakan `(1U << 7)` bukan `(1 << 7)`.
2. **Kompilasi dengan Deteksi Kesalahan Ketat:** Pasang konfigurasi compiler minimum untuk mendeteksi anomali representasi bit:
   ```bash
   gcc -std=c11 -Wall -Wextra -Wconversion -Wsign-conversion -pedantic -fsanitize=undefined main.c
   ```
   * `-Wconversion` dan `-Wsign-conversion`: Mengeluarkan peringatan saat terjadi implicit cast yang memotong bit atau mengubah tanda.
   * `-fsanitize=undefined` (UBSan): Menghentikan eksekusi secara instan saat terjadi runtime Undefined Behavior (misal: *signed integer overflow*).
3. **Dokumentasikan Endianness Protokol:** Pada berkas header interface, berikan anotasi jelas apakah API menerima data dalam format *Host Byte Order* atau *Network Byte Order*.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Branchless Bitwise Math
Operasi percabangan (`if-else`) dapat menyebabkan *branch misprediction* yang mengosongkan *pipeline* prosesor modern. Banyak kondisi biner dapat digantikan dengan trik bitwise branchless:

* **Mengecek apakah integer unsigned adalah kelipatan kuadrat dari 2 ($2^k$):**
  ```c
  bool is_power_of_two = (val != 0) && ((val & (val - 1)) == 0);
  ```
* **Mendapatkan Nilai Minimum tanpa Branching:**
  ```c
  int32_t min(int32_t x, int32_t y) {
      return y + ((x - y) & ((x - y) >> 31));
  }
  ```

### 2. Builtin Compiler Intrinsics
Untuk performa tertinggi dalam pemrosesan bit, hindari algoritma perulangan manual dan gunakan instruksi intrinsik bawaan CPU yang dipetakan langsung ke instruksi mesin khusus:
* Menghitung bit 1 (*Population Count*): `__builtin_popcount(val)` (Instruksi assembly x86: `POPCNT`).
* Menghitung nol di posisi signifikan terdepan (*Count Leading Zeros*): `__builtin_clz(val)` (Instruksi assembly: `BSR`/`LZCNT`).

---

## SEKSI 16 — KEAMANAN & HARDENING

### Penanganan Integer Overflow (Mitigasi CWE-190)
Salah satu celah kerentanan peretasan sistem C paling mematikan terjadi ketika penghitungan ukuran alokasi memori mengalami *integer overflow*, menghasilkan alokasi buffer kecil yang kemudian dieksploitasi dengan *buffer overflow*.

**Pola Rawan Eksploitasi:**
```c
void *allocate_array(size_t num_elements, size_t element_size) {
    // Jika num_elements * element_size meluap (overflow), 
    // alokasi akan berukuran kecil, memicu eksploitasi Heap Overflow
    return malloc(num_elements * element_size);
}
```

**Pola Aman Standar Produksi (Hardened):**
```c
#include <limits.h>
#include <stdlib.h>

void *allocate_array_hardened(size_t num_elements, size_t element_size) {
    if (num_elements == 0 || element_size == 0) {
        return NULL;
    }
    // Verifikasi matematis apakah terjadi overflow sebelum perkalian dilakukan
    if (num_elements > SIZE_MAX / element_size) {
        // Log security alert: Deteksi upaya overflow!
        return NULL; 
    }
    return malloc(num_elements * element_size);
}
```
*Catatan C11/GCC 5+:* Gunakan fungsi bawaan aman seperti `__builtin_mul_overflow(num_elements, element_size, &total)` untuk mendeteksi luapan menggunakan flag perangkat keras ALU secara langsung.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Debugging Format Bit pada GDB (GNU Debugger)
Saat melakukan debugging pada target biner, instruksi cetak standar tidak memadai. Manfaatkan format internal GDB:

* **Mencetak Biner:** Perintah `p/t variabel` mencetak representasi biner secara instan.
  ```gdb
  (gdb) print/t current_byte
  $1 = 10100010
  ```
* **Mencetak Memori Hex Dump:** Perintah `x/nfu address` (*examine memory*):
  * `x/8xb &buffer` : Tampilkan 8 byte dalam format hexadesimal.
  * `x/4tw &buffer` : Tampilkan 4 word (32-bit) dalam format binary bit.
* **Memeriksa Register CPU:**
  ```gdb
  (gdb) info registers eflags
  ```
  Ini menampilkan status flag ALU aktif (seperti Carry, Overflow, Sign).

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### 1. Operasi Bitwise Utama

| Operator | Operasi Simbolik | Ekspresi C | Tujuan Umum Rekayasa |
| :--- | :--- | :--- | :--- |
| **SET** | Mengaktifkan bit ke-n menjadi 1 | `x |= (1U << n)` | Mengaktifkan flag kontrol peripheral. |
| **CLEAR** | Mengosongkan bit ke-n menjadi 0 | `x &= ~(1U << n)` | Mematikan flag atau interrupt. |
| **TOGGLE** | Membalik nilai bit ke-n | `x ^= (1U << n)` | Mengubah status pin I/O secara periodik. |
| **CHECK** | Memeriksa apakah bit ke-n aktif | `(x & (1U << n)) != 0` | Polling register status hardware. |

### 2. Spesifikasi Tipe Data Minimum (C99 `<stdint.h>`)

| Nama Tipe | Lebar Bit | Rentang Nilai Minimum / Pasti | Format Specifier |
| :--- | :--- | :--- | :--- |
| `int8_t` | 8 bit | -128 s.d. 127 | `PRId8` / `"%d"` |
| `uint8_t`| 8 bit | 0 s.d. 255 | `PRIu8` / `"%u"` |
| `int16_t`| 16 bit | -32,768 s.d. 32,767 | `PRId16` / `"%d"` |
| `uint16_t`| 16 bit| 0 s.d. 65,535 | `PRIu16` / `"%u"` |
| `int32_t`| 32 bit | -2,147,483,648 s.d. 2,147,483,647 | `PRId32` / `"%d"` |
| `uint32_t`| 32 bit| 0 s.d. 4,294,967,295 | `PRIu32` / `"%u"` |
| `int64_t`| 64 bit | $\approx -9.22 \times 10^{18}$ s.d. $\approx 9.22 \times 10^{18}$ | `PRId64` / `"%lld"` |
| `uint64_t`| 64 bit| 0 s.d. $\approx 1.84 \times 10^{19}$ | `PRIu64` / `"%llu"` |

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Ujilah pemahaman Anda secara mandiri sebelum melangkah ke proyek mini.

### Soal Tingkat Dasar (Basic)
1. Apa representasi heksadesimal dari nilai `-2` jika disimpan pada variabel bertipe `int8_t`?
2. Mengapa operasi `uint8_t a = 255; a = a + 1;` tidak memicu *Undefined Behavior*?
3. Apa perbedaan mendasar antara *Arithmetic Right Shift* dan *Logical Right Shift*?
4. Jika variabel `uint32_t x = 0x12345678` disimpan pada sistem *Little-Endian*, byte apa yang berada di alamat memori terendah?
5. Mengapa perbandingan floating-point `if (0.1f + 0.2f == 0.3f)` sering kali bernilai *false*?

### Soal Tingkat Menengah (Intermediate)
6. Diberikan kode: `int8_t val = -1; uint32_t res = (uint32_t)val;`. Apakah nilai variabel `res` dalam format heksadesimal? Jelaskan mekanisme internalnya!
7. Ekspresi bitwise manakah yang secara deterministik mengosongkan (*clear*) satu bit bernilai 1 paling kanan (*least significant set bit*) dari sebuah integer tanpa perulangan?
8. Diberikan kode:
   ```c
   uint16_t x = 10;
   uint32_t y = ~x;
   ```
   Mengapa nilai `y` menghasilkan `0xFFFFFFF5` dan bukan `0x0000FFF5` pada sistem 32-bit?
9. Jelaskan bahaya keamanan dari implementasi penambahan integer berikut:
   ```c
   bool is_addition_safe(int32_t a, int32_t b) {
       return (a + b) >= a; // Analisis keabsahan logika ini!
   }
   ```
10. Bagaimana representasi IEEE 754 mengkodekan nilai matematika tak hingga (*Positive Infinity*)?

---

### Kunci Jawaban & Pembahasan Kuis

1. **`0xFE`**. Dalam 8-bit Two's complement: `+2` adalah `00000010`. Invert: `11111101`. Tambah 1: `11111110` (`0xFE`).
2. Karena standar ISO C secara eksplisit mendefinisikan bahwa aritmetika bilangan *unsigned* bersifat modular modulo $2^N$. Nilai `255 + 1` berputar (*wraparound*) secara legal menjadi `0`.
3. *Logical Shift* selalu menyisipkan bit `0` di posisi kiri yang ditinggalkan. *Arithmetic Shift* menduplikasi bit tanda (MSB) pada bit yang masuk untuk menjaga polaritas tanda negatif pada representasi komplemen dua.
4. **`0x78`**. Sistem Little-Endian menempatkan *Least Significant Byte* (LSB) pada alamat memori fisik yang paling rendah.
5. Karena basis bilangan biner pecahan tidak dapat merepresentasikan angka desimal persepuluhan (`0.1`) secara eksak tanpa desimal berulang tak terhingga (mirip $1/3$ dalam desimal). Presisi terpotong pada mantissa 23-bit, menyebabkan *rounding error*.
6. **`0xFFFFFFFF`**. Tipe `int8_t` (-1) mengalami *Sign Extension* saat dinaikkan ke integer sistem (`0xFFFFFFFF`), kemudian ditransformasikan ke pembacaan `uint32_t` dengan pola bit yang dipertahankan utuh.
7. Ekspresi: **`x & (x - 1)`**. Mengurangkan 1 akan membalik bit 1 paling kanan beserta seluruh bit 0 di sebelah kanannya menjadi 1. Melakukan operasi AND dengan nilai awal akan memadamkan bit tersebut.
8. Akibat **Integer Promotion**. Operand `x` dipromosikan terlebih dahulu menjadi `int` (32-bit signed: `0x0000000A`). Operasi inversi bitwise `~` membalik seluruh 32 bit tersebut menjadi `0xFFFFFFF5`.
9. **Logika tersebut tidak valid dan dieliminasi oleh compiler!** Jika `a + b` menghasilkan overflow, operasi tersebut merupakan *Signed Integer Overflow (Undefined Behavior)*. Compiler modern mengasumsikan UB tidak pernah terjadi, sehingga secara matematis `a + b >= a` dianggap selalu bernilai `true` (jika $b \ge 0$) dan pemeriksaan keamanan tersebut dihapus saat optimasi diaktifkan (`-O2`).
10. *Positive Infinity* dikodekan dengan: **Sign Bit = 0**, seluruh bit **Exponent = 1** (nilai 255 pada single precision), dan seluruh bit **Mantissa = 0**.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Tantangan Pemrograman: Universal Binary Sensor Frame Encoder & Decoder

Tulis program C standar mandiri (satu file `.c`) yang mengimplementasikan sistem packing data telemetri kompresi bit tinggi untuk sensor navigasi drone dengan spesifikasi berikut:

#### Spesifikasi Frame (Panjang Tepat 4 Byte / 32 Bit):
1. **Latitude Offset (10 bit signed):** Rentang -512 s.d. +511. (Bit 31..22)
2. **Longitude Offset (10 bit signed):** Rentang -512 s.d. +511. (Bit 21..12)
3. **Altitude Raw (8 bit unsigned):** Rentang 0 s.d. 255 meter. (Bit 11..4)
4. **Engine Status (2 bit unsigned):** Status 0..3 (0: Stop, 1: Idle, 2: Run, 3: Overheat). (Bit 3..2)
5. **Parity Bit (2 bit):** Bit 1 adalah *Even Parity* dari 16-bit teratas; Bit 0 adalah *Odd Parity* dari 16-bit terbawah. (Bit 1..0)

#### Tugas Eksekusi:
1. Implementasikan fungsi encoder:
   ```c
   uint32_t pack_telemetry(int16_t lat, int16_t lon, uint8_t alt, uint8_t engine);
   ```
2. Implementasikan fungsi decoder:
   ```c
   bool unpack_telemetry(uint32_t packet, int16_t *lat, int16_t *lon, uint8_t *alt, uint8_t *engine);
   ```
3. Pastikan penanganan *sign extension* untuk nilai negatif 10-bit bekerja sempurna (nilai negatif `-250` harus terdekode kembali tepat `-250`, bukan nilai positif).
4. Validasi kedua bit paritas pada fungsi decoder. Kembalikan `false` jika data terkorupsi.
5. Uji program Anda dengan mengompilasi menggunakan flag ketat:
   ```bash
   gcc -std=c99 -Wall -Wextra -Werror -pedantic mini_project.c -o mini_project
   ```