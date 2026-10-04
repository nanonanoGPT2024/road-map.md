# Bab 06 Module 01: Tipe Data Buatan: Struct, Union, Enum, & Memory Alignment

---

## SEKSI 01 — IDENTITAS MODUL

*   **Modul ID:** `MOD-C-06-01`
*   **Jalur Kurikulum:** `02-Programming-Languages / c`
*   **Tingkat Kesulitan:** Intermediate to Advanced
*   **Prasyarat Konseptual:**
    *   Representasi data primitif dan integer sizing (`stdint.h`).
    *   Aritmatika pointer dan dereferensi memori.
    *   Organisasi memori C: Stack, Heap, Data Segment.
*   **Kebutuhan Lingkungan:**
    *   Kompilator: GCC (versi 9.x+) atau Clang (versi 10.x+).
    *   Standar C: C99 / C11 (`-std=c11 -Wall -Wextra -pedantic`).
    *   Debugger & Analisis: GDB, Valgrind (`valgrind --tool=memcheck`).
    *   Arsitektur Target Diskusi: x86_64 (64-bit Little Endian ABI).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis (Analyze):** Mengurai struktur internal memori dari tipe komposit (`struct` dan `union`), menghitung lokasi *offset* setiap *member*, serta mengidentifikasi keberadaan *padding bytes* akibat batasan arsitektur CPU.
2.  **Mengevaluasi (Evaluate):** Menilai dampak performa dan konsumsi memori dari deklarasi *struct* yang tidak optimal, serta mengevaluasi legalitas akses *member union* berdasarkan aturan *strict aliasing* C99/C11.
3.  **Mengoptimalkan (Optimize):** Menyusun ulang (*reordering*) deklarasi *member struct* untuk mereduksi fragmentasi memori internal (*internal padding*) hingga mencapai densitas data optimal tanpa merusak fungsionalitas.
4.  **Mengimplementasikan (Create):** Mengembangkan arsitektur *Tagged Union* (Variant Record) yang aman untuk sistem pengolahan pesan biner (*binary packet parser*) berbasis bit-field dan enumerasi terkontrol.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Kompilator adalah Akuntan Memori, CPU adalah Operator Kata (*Word*)

Dalam paradigma bahasa C, abstraksi tipe data tidak menyembunyikan realitas fisik perangkat keras. Seorang perekayasa perangkat lunak sistem tidak boleh memandang `struct` sebagai kumpulan variabel logis semata, melainkan sebagai **templat tata letak memori linier contiguous**.

CPU modern tidak membaca memori dalam hitungan bita tunggal (*single byte*) secara terisolasi saat mengeksekusi instruksi aritmatika atau register loading. CPU membaca data melalui *memory bus* dalam ukuran *word* (misalnya 4 bita pada arsitektur 32-bit, atau 8 bita pada arsitektur 64-bit).

```
                 ALAMAT MEMORI DAPAT DIBAGI 8 (Word-Aligned)
[ 0x00 ] [ 0x01 ] [ 0x02 ] [ 0x03 ] | [ 0x04 ] [ 0x05 ] [ 0x06 ] [ 0x07 ]
-------------------------------------------------------------------------
|               1 Siklus Bus Memory Read (8 Bytes Sekaligus)            |
```

Ketika Anda meletakkan tipe data 4-bita (`uint32_t`) pada alamat ganjil (misal `0x03`), CPU harus:
1. Melakukan dua kali siklus *memory access bus* (`0x00-0x07` dan `0x08-0x0F`).
2. Melakukan operasi *shifting* dan *masking* bita secara internal untuk merekonstruksi nilai integer tersebut.
3. Pada arsitektur tertentu (misal ARM lama atau MIPS), akses *unaligned* ini memicu hardware exception/trap (`SIGBUS`).

Oleh karena itu, kompilator secara otomatis menyisipkan **padding** untuk memastikan data berada pada batas (*boundary*) yang merupakan kelipatan dari ukurannya sendiri (*Natural Alignment*). Mental model yang benar: **Kompilator mengorbankan ruang memori demi menyelamatkan siklus komputasi CPU.**

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Perbandingan Layout Memori: Unaligned vs Aligned Struct

Ditinjau dari sebuah `struct` sederhana:
```c
struct Sample {
    char   a; // 1 Byte
    int    b; // 4 Byte
    short  c; // 2 Byte
};
```

```
LAYOUT TIDAK DIOPTIMASI (Ukuran Total: 12 Bytes)
Offset:
0x00      0x01      0x02      0x03      0x04                0x07 0x08      0x09      0x0A      0x0B
+---------+---------+---------+---------+---------+---------+----+---------+---------+---------+---------+
|    a    |   PAD   |   PAD   |   PAD   |         b              |    c    |   PAD   |   PAD   |
| (1 B)   | (Padding byte: 3 B)         |      (4 Bytes)         |  (2 B)  | (Tail Padding: 2 B) |
+---------+---------+---------+---------+---------+---------+----+---------+---------+---------+---------+

LAYOUT DIOPTIMASI (Reordered: int b; short c; char a; -> Ukuran Total: 8 Bytes)
Offset:
0x00                0x03 0x04      0x05 0x06      0x07
+---------+---------+----+---------+----+---------+---------+
|         b              |    c         |    a    |   PAD   |
|      (4 Bytes)         |  (2 B)       |  (1 B)  |  (1 B)  |
+---------+---------+----+---------+----+---------+---------+
```

### 2. Layout Overlapping Union vs Sequential Struct

```
STRUCT LAYOUT (Independen: Ukuran = sum(members) + padding)
Offset:  0x00      0x03 0x04 0x05 0x06      0x07
         +-------------+----+----+-------------+
Data:    |   int32_t   | c1 | c2 |   Padding   |
         +-------------+----+----+-------------+

UNION LAYOUT (Tumpang Tindih / Shared Storage: Ukuran = max(member_size) + tail_pad)
Offset:  0x00      0x01      0x02      0x03
         +---------+---------+---------+---------+
int32_t: | Byte 0  | Byte 1  | Byte 2  | Byte 3  |
         +---------+---------+---------+---------+
float:   | IEEE 754 floating-point representation|
         +---------+---------+---------+---------+
uint8_t: | uint8_t | (sisa ruang tidak dipakai)  |
         +---------+-----------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Padding dan Aturan Natural Alignment

Aturan penyusunan memori pada ABI C standar (misal System V AMD64 ABI):
*   Tipe data berukuran $N$ bita harus berlokasi pada alamat memori yang habis dibagi $N$ (`Address % N == 0`).
    *   `char` (1 bita): sembarang alamat.
    *   `int16_t` (2 bita): alamat genap (`0x...0`, `0x...2`, dst.).
    *   `int32_t` (4 bita): alamat kelipatan 4 (`0x...0`, `0x...4`, dst.).
    *   `int64_t` / Pointer (8 bita): alamat kelipatan 8 (`0x...0`, `0x...8`, dst.).
*   **Total Alignment Struct ($S_{align}$):** Ditentukan oleh *member* dengan alignment requirement terbesar.
*   **Tail Padding:** Ukuran total `struct` harus merupakan kelipatan bulat dari $S_{align}$. Ini menjamin jika `struct` dialokasikan dalam bentuk *array*, elemen kedua (`array[1]`) tetap berada pada alignment requirement yang benar.

### 2. Bit-Fields Internal Packing

C mengizinkan deklarasi variabel pada resolusi bita level sub-byte (*bit-level*):
```c
struct Flags {
    uint8_t is_ready : 1;
    uint8_t mode     : 3;
    uint8_t error    : 4;
};
```
*   Kompilator mengemas (*pack*) bit-fields ke dalam *allocation unit* sesuai tipe basisnya (`uint8_t` = 1 bita alokasi, `uint32_t` = 4 bita alokasi).
*   **Peringatan Keras Kompatibilitas:** Urutan pengisian bit dalam unit alokasi (apakah dari LSB ke MSB, atau MSB ke LSB) adalah **implementation-defined** (tergantung target arsitektur dan kompilator). Jangan pernah mentransmisikan bit-field mentah (*raw*) langsung melalui soket jaringan antar sistem dengan arsitektur berbeda.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Struct: Komposisi Heterogen & Flexible Array Member (FAM)

Standar C99 memperkenalkan *Flexible Array Member* (FAM) untuk mengalokasikan payload dinamis tepat setelah struktur header, dalam satu blok memori contiguous:

```c
struct Packet {
    uint32_t length;
    uint16_t checksum;
    uint8_t  payload[]; // FAM: Harus diletakkan di akhir struct
};
```
Ukuran `sizeof(struct Packet)` hanya menghitung anggota statis (termasuk padding). Alokasi memori dilakukan dinamis:
```c
struct Packet *p = malloc(sizeof(struct Packet) + dynamic_payload_len);
```

### 2. Union: Mutually Exclusive Storage & Strict Aliasing

Union mengalokasikan memori yang setara dengan anggota terbesarnya, dialineasikan ke *member* dengan alignment requirement tertinggi.

**Strict Aliasing Rule (C99 §6.5/7):**
Dua pointer dari tipe yang berbeda tidak boleh menunjuk ke lokasi memori yang sama, kecuali salah satunya adalah `char*`. Pelanggaran aturan ini menghasilkan *Undefined Behavior* (UB) karena kompilator berhak mengasumsikan dereferensi pointer tersebut independen dalam optimasi register caching.

Namun, C99/C11 secara eksplisit melegalkan type punning via **Union** (§6.5.2.3 footnote 95): Membaca *member* union yang tidak aktif adalah valid, asalkan interpretasi bita merepresentasikan nilai yang legal.

### 3. Enum: Typed Named Constants

Enumerasi mendefinisikan konstanta simbolik bertipe bilangan bulat. Secara default dalam standar C, tipe dasar enumerasi dipromosikan ke `int`. Nilai pertama bernilai `0` jika tidak diinisialisasi secara eksplisit.
*   Keuntungan dibandingkan `#define`: Menghormati *lexical scope*, dapat diinspeksi oleh symbolic debugger (GDB), dan memberikan keamanan tipe dasar pada analisis statis.

### 4. Directives Alignment C11

Standar C11 memperkenalkan pustaka `<stdalign.h>`:
*   `alignof(type)`: Mengembalikan alignment requirement (ekuivalen operator `_Alignof`).
*   `alignas(expression)`: Memaksa batas alignment variabel atau struct (ekuivalen `_Alignas`).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode dasar demonstrasi perhitungan alignment, deteksi padding menggunakan makro standar `offsetof` dari `<stddef.h>`, implementasi bit-field, dan union.

```c
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <stdalign.h>

// Struct A: Susunan sembrono (Penuh Padding)
struct BadLayout {
    uint8_t  flag1;      // 1 Byte
    uint64_t large_id;   // 8 Byte
    uint16_t counter;    // 2 Byte
    uint32_t timestamp;  // 4 Byte
};

// Struct B: Susunan dioptimalkan (Diurutkan dari alignment terbesar ke terkecil)
struct OptimizedLayout {
    uint64_t large_id;   // 8 Byte
    uint32_t timestamp;  // 4 Byte
    uint16_t counter;    // 2 Byte
    uint8_t  flag1;      // 1 Byte
                         // 1 Byte Tail Padding otomatis ditambahkan kompilator
};

// Tagged Union sederhana
enum ValueType {
    VAL_INT,
    VAL_FLOAT
};

union DataHolder {
    int32_t i_val;
    float   f_val;
};

struct VariantValue {
    enum ValueType type;
    union DataHolder data;
};

int main(void) {
    printf("=== ANALISIS MEMORI STRUCT & ALIGNMENT ===\n");
    printf("Size of struct BadLayout: %zu bytes (Alignment: %zu)\n", 
            sizeof(struct BadLayout), alignof(struct BadLayout));
    printf("  offset flag1:      %zu\n", offsetof(struct BadLayout, flag1));
    printf("  offset large_id:   %zu (Internal pad: %zu bytes)\n", 
            offsetof(struct BadLayout, large_id), 
            offsetof(struct BadLayout, large_id) - sizeof(uint8_t));
    printf("  offset counter:    %zu\n", offsetof(struct BadLayout, counter));
    printf("  offset timestamp:  %zu (Internal pad: %zu bytes)\n\n", 
            offsetof(struct BadLayout, timestamp),
            offsetof(struct BadLayout, timestamp) - (offsetof(struct BadLayout, counter) + sizeof(uint16_t)));

    printf("Size of struct OptimizedLayout: %zu bytes (Alignment: %zu)\n", 
            sizeof(struct OptimizedLayout), alignof(struct OptimizedLayout));
    printf("  offset large_id:   %zu\n", offsetof(struct OptimizedLayout, large_id));
    printf("  offset timestamp:  %zu\n", offsetof(struct OptimizedLayout, timestamp));
    printf("  offset counter:    %zu\n", offsetof(struct OptimizedLayout, counter));
    printf("  offset flag1:      %zu\n\n", offsetof(struct OptimizedLayout, flag1));

    printf("=== OPERASI TAGGED UNION ===\n");
    struct VariantValue val;
    val.type = VAL_FLOAT;
    val.data.f_val = 3.14159f;

    if (val.type == VAL_FLOAT) {
        printf("Tipe Data: FLOAT, Nilai: %f\n", val.data.f_val);
    }

    // Type Punning: Mengakses raw bits integer dari floating point
    printf("Representasi Hexadecimal IEEE 754: 0x%08X\n", (unsigned int)val.data.i_val);

    return 0;
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 6–12:** Deklarasi `struct BadLayout`. `flag1` berukuran 1 bita terletak pada offset 0. Variabel berikutnya `large_id` bertipe `uint64_t` memerlukan batas alamat kelipatan 8. Kompilator menyisipkan 7 bita padding pada offset 1 hingga 7.
*   **Baris 14–21:** Deklarasi `struct OptimizedLayout`. Anggota diurutkan secara monoton turun berdasarkan alignment: 8-byte (`large_id`), 4-byte (`timestamp`), 2-byte (`counter`), lalu 1-byte (`flag1`). Hanya tersisa 1 bita *tail padding* pada offset 15 untuk memenuhi kelipatan 8 dari total ukuran struct (16 bita).
*   **Baris 24–36:** Deklarasi idiom *Tagged Union*. Enum `ValueType` bertindak sebagai penanda (*discriminator*) untuk menentukan field mana dalam `union DataHolder` yang sah untuk dibaca.
*   **Baris 40–54:** Penggunaan `sizeof` dan `offsetof` dari `<stddef.h>`. Makro `offsetof(type, member)` menghitung jarak bita dari awal basis struct ke anggota target secara presisi tanpa memicu instansiasi objek.
*   **Baris 67:** Membaca `val.data.i_val` setelah menulis ke `val.data.f_val`. Pada C99/C11, operasi ini adalah *well-defined type punning*, yang membaca representasi bita biner mentah dari bilangan float IEEE 754 tanpa overhead konversi komputasi (`fistp` / `cvtsi2ss`).

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: High-Performance Network Telemetry Packet Decoder

Dalam telemetri *Internet-of-Things* (IoT) berkecepatan tinggi atau perangkat jaringan (router/switch), paket data biner dikirim melalui soket UDP mentah. Setiap frame memiliki tipe payload bervariasi: status sensor suhu/kelembaban, paket diagnostik jaringan, atau event alarm darurat.

**Permasalahan:**
1. Deserialisasi paket tidak boleh menggunakan alokasi dinamis berulang (`malloc`/`free`) per paket karena dapat menyebabkan fragmentasi heap dan latensi tinggi.
2. Ukuran memori payload bersifat dinamis dan heterogen.
3. Deserializer harus memvalidasi integritas sebelum mengizinkan pemrosesan lebih lanjut untuk mencegah *out-of-bounds read*.

**Solusi Arsitektural:**
Membangun sebuah *Zero-Copy In-Place Packet Parser* menggunakan:
*   `enum` untuk opcode instruksi protokol.
*   Bit-fields untuk representasi header kendali kompak.
*   `union` untuk payload heterogen.
*   `struct` dengan *Flexible Array Member* untuk *buffer payload* dinamis.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Simpan implementasi berikut dalam berkas `telemetry_parser.c`:

```c
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdalign.h>

// Definisi Opcode Telemetri
typedef enum : uint8_t {
    OPCODE_ENVIRONMENTAL = 0x01,
    OPCODE_SYSTEM_STATUS = 0x02,
    OPCODE_CRITICAL_ALERT = 0x03
} TelemetryOpcode;

// Control Flags Header menggunakan bit-field (1 Byte)
typedef struct {
    uint8_t is_encrypted : 1;
    uint8_t priority     : 2;
    uint8_t version      : 5;
} PacketHeaderFlags;

// Payload 1: Environmental (8 Bytes)
typedef struct {
    int16_t  temperature_celsius; // Skala 0.01 C
    uint16_t humidity_percent;    // Skala 0.01 %
    uint32_t atmospheric_pa;      // Pascal
} EnvironmentalPayload;

// Payload 2: System Status (8 Bytes)
typedef struct {
    uint32_t uptime_seconds;
    uint16_t battery_millivolts;
    uint8_t  cpu_load_percent;
    uint8_t  reserved;
} SystemStatusPayload;

// Payload 3: Critical Alert (8 Bytes)
typedef struct {
    uint32_t alert_code;
    uint32_t fault_address;
} CriticalAlertPayload;

// Discriminative Tagged Record: Ukuran union fix 8 bita
typedef union {
    EnvironmentalPayload env;
    SystemStatusPayload  sys;
    CriticalAlertPayload alert;
    uint8_t              raw_bytes[8];
} TelemetryPayload;

// Paket Lengkap yang diterima (Strict Memory Aligned Header)
typedef struct {
    PacketHeaderFlags flags;
    TelemetryOpcode   opcode;
    uint16_t          sequence_number;
    uint32_t          payload_crc;
    TelemetryPayload  data;
} TelemetryFrame;

// Simple Checksum Function (CRC-32 Placeholder: XOR Checksum untuk contoh ini)
static uint32_t calculate_checksum(const uint8_t *data, size_t len) {
    uint32_t checksum = 0xEDB88320;
    for (size_t i = 0; i < len; ++i) {
        checksum ^= (uint32_t)data[i];
        for (int j = 0; j < 8; ++j) {
            checksum = (checksum >> 1) ^ (0xEDB88320 & (-(checksum & 1)));
        }
    }
    return checksum;
}

// Zero-copy processing function
void process_packet(const uint8_t *raw_stream, size_t stream_size) {
    if (stream_size < sizeof(TelemetryFrame)) {
        fprintf(stderr, "[ERROR] Paket truncate: Ukuran %zu bita < Minimum %zu bita\n", 
                stream_size, sizeof(TelemetryFrame));
        return;
    }

    // Hindari unaligned direct casting! Salin via memcpy atau gunakan pointer aligned
    TelemetryFrame frame;
    memcpy(&frame, raw_stream, sizeof(TelemetryFrame));

    // Validasi Integritas Payload via CRC
    uint32_t computed_crc = calculate_checksum(frame.data.raw_bytes, sizeof(TelemetryPayload));
    if (computed_crc != frame.payload_crc) {
        fprintf(stderr, "[ALERT] Corrupt CRC: Dihitung=0x%08X, Didapat=0x%08X\n", 
                computed_crc, frame.payload_crc);
        return;
    }

    printf("=== DITERIMA TELEMETRY FRAME [Seq: %u] ===\n", frame.sequence_number);
    printf("Header: Ver=%u, Priority=%u, Encrypted=%s\n", 
           frame.flags.version, frame.flags.priority, 
           frame.flags.is_encrypted ? "YES" : "NO");

    switch (frame.opcode) {
        case OPCODE_ENVIRONMENTAL:
            printf("Payload Type: Environmental\n");
            printf("  Suhu: %.2f C\n", frame.data.env.temperature_celsius / 100.0f);
            printf("  Kelembaban: %.2f %%\n", frame.data.env.humidity_percent / 100.0f);
            printf("  Tekanan: %u Pa\n", frame.data.env.atmospheric_pa);
            break;

        case OPCODE_SYSTEM_STATUS:
            printf("Payload Type: System Status\n");
            printf("  Uptime: %u detik\n", frame.data.sys.uptime_seconds);
            printf("  Baterai: %u mV\n", frame.data.sys.battery_millivolts);
            printf("  CPU Load: %u %%\n", frame.data.sys.cpu_load_percent);
            break;

        case OPCODE_CRITICAL_ALERT:
            printf("[WARNING] Payload Type: CRITICAL ALERT\n");
            printf("  Alert Code: 0x%08X\n", frame.data.alert.alert_code);
            printf("  Fault Addr: 0x%08X\n", frame.data.alert.fault_address);
            break;

        default:
            fprintf(stderr, "[ERROR] Opcode tidak dikenal: 0x%02X\n", frame.opcode);
            break;
    }
    printf("----------------------------------------\n\n");
}

int main(void) {
    // Simulasi pembuatan paket dari transmisi jaringan (Little Endian System)
    TelemetryFrame tx_frame;
    memset(&tx_frame, 0, sizeof(TelemetryFrame));

    // Siapkan Header
    tx_frame.flags.version = 1;
    tx_frame.flags.priority = 3;
    tx_frame.flags.is_encrypted = 0;
    tx_frame.opcode = OPCODE_ENVIRONMENTAL;
    tx_frame.sequence_number = 1024;

    // Siapkan Data
    tx_frame.data.env.temperature_celsius = 2845; // 28.45 C
    tx_frame.data.env.humidity_percent = 6520;    // 65.20 %
    tx_frame.data.env.atmospheric_pa = 101325;    // 101325 Pa

    // Hitung Checksum
    tx_frame.payload_crc = calculate_checksum(tx_frame.data.raw_bytes, sizeof(TelemetryPayload));

    // Simulasikan raw buffer transmisi biner
    uint8_t binary_buffer[sizeof(TelemetryFrame)];
    memcpy(binary_buffer, &tx_frame, sizeof(TelemetryFrame));

    // Parsing frame valid
    process_packet(binary_buffer, sizeof(binary_buffer));

    // Simulasi paket korup (Data diubah secara sengaja di transmisi)
    binary_buffer[12] ^= 0xFF; // Merusak bita payload
    process_packet(binary_buffer, sizeof(binary_buffer));

    return 0;
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Desain Struktur: Packed Struct vs Aligned Struct

| Atribut / Metrik | Aligned Struct (Default) | Packed Struct (`#pragma pack(1)` / `__attribute__((packed))`) |
| :--- | :--- | :--- |
| **Konsumsi Memori** | Terdapat *internal/tail padding*, ukuran memori lebih besar. | Densitas 100%, ukuran memori minimal (tanpa padding). |
| **Kecepatan Akses CPU** | Maksimal: Menggunakan instruksi tunggal register CPU native. | Lambat: CPU terpaksa melakukan multi-cycle memory fetch & shift. |
| **Portabilitas Hardware** | Aman untuk seluruh arsitektur prosesor (x86, ARM, RISC-V). | Bahaya: Memancing *Unaligned Memory Access Fault* (`SIGBUS`) pada ARM/SPARC. |
| **Serialisasi Biner** | Tidak cocok dikirim langsung ke jaringan (tergantung ABI kompilator). | Sangat mudah dipetakan langsung ke frame protokol hardware/jaringan. |

### 2. Konstruksi Tipe Data: Struct vs Union

| Karakteristik | `struct` | `union` |
| :--- | :--- | :--- |
| **Layout Memori** | Seluruh anggota tersusun secara berurutan (*sequential*). | Semua anggota berbagi lokasi alamat awal yang persis sama (*overlapping*). |
| **Alokasi Ukuran** | $\ge \sum \text{ukuran anggota}$ (akibat adanya padding). | Tergantung ukuran anggota terbesar ($\max(\text{size}) + \text{tail pad}$). |
| **Waktu Hidup Variabel** | Seluruh anggota dapat diakses secara simultan dan independen. | Hanya satu anggota yang merepresentasikan data valid dalam satu waktu. |
| **Use Case Utama** | Agregasi data (Domain Object, Entitas, State). | Penghematan memori, Rekayasa Varian Data, Type Punning. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Kebocoran Informasi (*Information Leak*) via Padding Bytes
Jika sebuah struct dialokasikan di stack:
```c
struct SecretPacket {
    char flag;
    // 3 bytes padding tak terinisialisasi (menyimpan data memori lama stack)
    int secret_key;
};
```
Mengirim struct tersebut via `send(socket, &pkt, sizeof(pkt), 0)` akan mengekspos isi 3 bita padding yang berada di stack ke jaringan. Ini berpotensi membocorkan pointer memori lama, token otentikasi, atau sisa enkripsi sebelumnya (*Heartbleed-like leak*).
*Mitigasi:* Selalu bersihkan struct dengan `memset(&pkt, 0, sizeof(pkt))` sebelum mengisi anggota atau mentransmisikannya.

### 2. Strict Aliasing Violation Melalui Raw Casting
Melakukan dereferensi pointer seperti ini:
```c
uint32_t val = 0x41424344;
float f = *(float*)&val; // UNDEFINED BEHAVIOR: Pelanggaran Strict Aliasing!
```
Kompilator yang mengoptimasi dengan `-O2` atau `-O3` berhak mengatur ulang eksekusi instruksi register sehingga menghasilkan data acak.
*Solusi yang Sah secara Standar C:*
Gunakan `memcpy(&f, &val, sizeof(float))` atau gunakan **Union Type Punning**.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Membandingkan Dua Struct Menggunakan `memcmp`
```c
// KESALAHAN FATAL
struct Point { char x; int y; };
struct Point p1 = {'A', 10};
struct Point p2 = {'A', 10};

if (memcmp(&p1, &p2, sizeof(struct Point)) == 0) { ... }
```
**Mengapa salah:** Padding bytes berisi data acak jika tidak diinisialisasi melalui `memset`. Walaupun `p1.x == p2.x` dan `p1.y == p2.y`, `memcmp` dapat menghasilkan evaluasi tidak sama (`false`) karena perbedaan nilai bita sampah pada area padding.
**Cara Menghindari:** Lakukan komparasi eksplisit untuk setiap field:
```c
bool is_equal = (p1.x == p2.x) && (p1.y == p2.y);
```

### 2. Mengabaikan Alignment pada Flexible Array Member
Mengalokasikan struct FAM tanpa memperhitungkan tipe alineasi anggota dinamis:
```c
struct Msg {
    uint8_t flags;
    uint64_t data[]; // Butuh alignment kelipatan 8 bita
};
```
Jika Anda menghitung alokasi secara naif: `malloc(sizeof(struct Msg) + n * sizeof(uint64_t))`, `sizeof(struct Msg)` sudah menyertakan padding yang diperlukan agar `data` teralineasikan secara valid ke kelipatan 8. Namun, jika Anda menggunakan pointer offset manual tanpa alokasi berbasis `sizeof`, Anda berisiko memicu akses unaligned.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Aturan Pengurutan Ukuran (Descending Size Order):** Urutkan anggota struct mulai dari tipe dengan alignment terbesar (64-bit/pointer), turun ke 32-bit, 16-bit, hingga 8-bit. Langkah ini secara matematis meminimalkan kebutuhan padding internal hingga ke level 0 bita (kecuali tail padding).
2.  **Explicit Padding Injection:** Untuk sistem berkeandalan tinggi (MISRA-C / Embedded / Kernel Dev), buat padding eksplisit terlihat dalam kode:
    ```c
    struct ExplicitBlock {
        uint32_t id;
        uint8_t  flag;
        uint8_t  _reserved[3]; // Padding dideklarasikan secara sadar
    };
    ```
3.  **Hindari Membuka Bit-field Langsung ke Layer Hardware:** Gunakan operasi bitmasking manual (`&`, `|`, `<<`) pada register perangkat keras untuk menjamin kebebasan dari perbedaan endianness arsitektur, kecuali jika driver ditulis spesifik untuk kompilator dan prosesor tertentu.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Struktur Array-of-Structures (AoS) vs Structure-of-Arrays (SoA)

```c
// AoS: Buruk untuk SIMD Vectorization dan Cache-locality jika hanya memproses satu atribut
struct ParticleAoS {
    float x, y, z;
    float vx, vy, vz;
};
struct ParticleAoS particles[10000];

// SoA: Luar biasa efisien untuk Cache Lines & AVX/SIMD Processing
struct ParticleSoA {
    float x[10000];
    float y[10000];
    float z[10000];
    float vx[10000];
    float vy[10000];
    float vz[10000];
};
```
Ketika mengiterasi ribuan partikel hanya untuk mengubah posisi `x` berdasarkan kecepatan `vx`, arsitektur **SoA** memuat data yang relevan secara berdekatan ke dalam L1 Data Cache (Cache Line 64-byte dapat memuat 16 nilai `float` sekaligus tanpa sampah koordinat `y` dan `z`).

### 2. Cache Line Alignment (`alignas(64)`)
Untuk arsitektur multi-core berkinerja tinggi, letakkan struct yang sering dimutasi oleh thread terpisah pada batas *Cache Line* independen (biasanya 64 bita) guna menghindari fenomena **False Sharing**:
```c
struct alignas(64) ThreadWorkerState {
    uint64_t counter; // Thread 1 menulis ke sini tanpa menginvalidasi cache Thread 2
};
```

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Integer Overflow saat Menghitung Alokasi FAM:**
    ```c
    size_t count = get_untrusted_count();
    // VULNERABILITY: Alokasi memori berisiko overflow jika count bernilai besar!
    // sizeof(Header) + count * sizeof(Item) dapat berputar kembali ke nilai kecil
    size_t alloc_size = sizeof(struct Header) + count * sizeof(uint32_t);
    struct Header *h = malloc(alloc_size); // Heap Overflow!
    ```
    *Mitigasi Hardening:* Gunakan pengecekan batas integer eksplisit sebelum perkalian dan penjumlahan:
    ```c
    if (count > (SIZE_MAX - sizeof(struct Header)) / sizeof(uint32_t)) {
        // Tolak request, alokasi berpotensi overflow
        return ERROR_OVERFLOW;
    }
    ```
2.  **Inisialisasi Seluruh Buffer Struct:**
    Selalu gunakan `= {0}` pada instansiasi stack:
    ```c
    struct TelemetryFrame frame = {0}; // Menjamin padding bita dinolkan (Zeroized)
    ```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Menginspeksi Layout Memori dengan GDB

Gunakan antarmuka debugging GDB untuk memverifikasi lokasi memori dan padding:
```bash
$ gcc -g telemetry_parser.c -o telemetry_parser
$ gdb ./telemetry_parser
(gdb) ptype /o struct TelemetryFrame
```
Perintah `ptype /o` akan menampilkan visualisasi struktur memori internal secara presisi:
```text
/* offset      |    size */  type = struct {
/*      0: 0   |       1 */    PacketHeaderFlags flags;
/*      1      |       1 */    TelemetryOpcode opcode;
/*      2      |       2 */    uint16_t sequence_number;
/*      4      |       4 */    uint32_t payload_crc;
/*      8      |       8 */    TelemetryPayload data;

                               /* total size (bytes):   16 */
                             }
```

### 2. Runtime Hex Dump Tool
Implementasikan macro diagnostik berikut untuk mencetak bita mentah dari variabel memori mana pun:
```c
void dump_memory(const void *ptr, size_t size) {
    const uint8_t *byte = (const uint8_t *)ptr;
    printf("[MEMDUMP %p, Size: %zu]\n  ", ptr, size);
    for (size_t i = 0; i < size; ++i) {
        printf("%02X ", byte[i]);
        if ((i + 1) % 8 == 0) printf(" ");
        if ((i + 1) % 16 == 0) printf("\n  ");
    }
    printf("\n");
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Natural Alignment:** Tipe data primitif berukuran $K$ bita harus memiliki alamat memori `ptr % K == 0`.
*   **Struct Padding:** Kompilator menyisipkan bita kosong (*padding*) di antara anggota struct untuk memastikan *natural alignment* setiap anggotanya, serta menyisipkan *tail padding* agar ukuran total struct habis dibagi *largest member alignment*.
*   **Optimasi Deklarasi Struct:** Selalu deklarasikan anggota dengan urutan menurun berdasarkan ukuran memori (8 bita $\rightarrow$ 4 bita $\rightarrow$ 2 bita $\rightarrow$ 1 bita) untuk mengeliminasi internal padding secara optimal.
*   **Union:** Mengalokasikan ruang memori yang sama untuk semua anggotanya. Ukuran total union minimal sebesar ukuran anggota terbesarnya. Digunakan untuk varian data polimorfik atau type-punning biner legal C99/C11.
*   **Enum:** Tipe nilai integer bernilai simbolis terkompilasi, menghormati scoping rule, dan secara default setara representasi `int`.
*   **Flexible Array Member (FAM):** Deklarasi `type arr[]` di akhir struct tanpa ukuran eksplisit, dialokasikan bersamaan dengan header struct melalui panggilan `malloc` tunggal.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Pengetahuan Dasar (Basic)

1.  Diberikan struct berikut pada sistem 64-bit standar:
    ```c
    struct Node {
        char val;
        double metric;
    };
    ```
    Berapakah nilai `sizeof(struct Node)`? Jelaskan perhitungannya!
    *Kunci Jawaban:* Nilai ukurannya adalah **16 bytes**. `char val` menempati offset 0 (1 bita). Anggota berikutnya `double metric` berukuran 8 bita dan wajib dialineasikan pada alamat kelipatan 8. Kompilator menyisipkan 7 bita padding pada offset 1 hingga 7. `metric` menempati offset 8 sampai 15. Total ukuran = $1 + 7 + 8 = 16$ bita.

2.  Apa yang dimaksud dengan *Tail Padding* dan apa fungsi krusialnya saat struct ditempatkan dalam sebuah *Array*?
    *Kunci Jawaban:* Tail padding adalah bita pengisi yang disematkan kompilator di bagian paling akhir struct. Fungsinya adalah memastikan bahwa jika struct dialokasikan sebagai array (`struct T arr[2]`), elemen berikutnya (`arr[1]`) akan langsung berada pada alamat memori yang memenuhi *alignment requirement* terbesar dari struct tersebut.

3.  Apakah anggota-anggota dalam sebuah `union` menempati alamat memori yang berbeda?
    *Kunci Jawaban:* **Tidak.** Seluruh anggota `union` dimulai dari basis alamat memori yang persis sama. Menulis nilai ke salah satu anggota union akan menimpa representasi bita anggota yang lain.

4.  Apa output dari potongan kode berikut berdasarkan standar C?
    ```c
    enum State { IDLE = 5, RUNNING, STOPPED = 10, ERROR };
    printf("%d, %d", RUNNING, ERROR);
    ```
    *Kunci Jawaban:* **6, 11**. Enumerator otomatis melanjutkan inkrementasi integer $+1$ dari nilai anggota sebelumnya jika tidak ditentukan secara eksplisit. `RUNNING` menjadi $5 + 1 = 6$, dan `ERROR` menjadi $10 + 1 = 11$.

5.  Sebutkan header standar C11 yang digunakan untuk mendapatkan fungsionalitas `alignof` dan `alignas`!
    *Kunci Jawaban:* `<stdalign.h>`.

---

### Soal Penerapan Lanjutan (Intermediate)

6.  Kapan penggunaan instruksi packed struct (`__attribute__((packed))`) dapat memicu performa komputasi menurun secara signifikan?
    *Kunci Jawaban:* Ketika membaca atau memodifikasi anggota multi-byte yang berlokasi pada alamat yang tidak sejajar (*unaligned*). Pada arsitektur yang mendukungnya (seperti x86), CPU membutuhkan ekstra siklus memori untuk membaca data dari dua segmen memori yang berbeda serta menyusunnya kembali. Pada arsitektur yang tidak mendukungnya (beberapa tipe ARM / MIPS), hal ini memicu sinyal interupsi hardware exception fault (`SIGBUS`).

7.  Ditinjau dari standar keamanan C, apa kerentanan yang muncul dari kode serialisasi data berikut?
    ```c
    void broadcast_state(int fd) {
        struct { char status; int id; } s;
        s.status = 'A';
        s.id = 1001;
        write(fd, &s, sizeof(s));
    }
    ```
    *Kunci Jawaban:* Variabel `s` dialokasikan di stack tanpa inisialisasi awal (`memset` atau zero initializer). Area padding 3 bita antara `status` dan `id` memuat data sampah dari eksekusi fungsi stack sebelumnya yang berpotensi mengekspos data rahasia (*uninitialized stack memory information leak*) ke soket `fd`.

8.  Mengapa deklarasi Flexible Array Member (`type arr[]`) dilarang diletakkan sebagai anggota pertama atau di tengah sebuah `struct`?
    *Kunci Jawaban:* Karena kompilator harus dapat menentukan *offset* konstan dari setiap anggota struct statis pada saat kompilasi (*compile-time constant offset*). Meletakkan array dinamis di awal atau di tengah akan menyebabkan offset dari anggota-anggota setelahnya menjadi tidak terdefinisi secara statis.

9.  Apakah kode modifikasi nilai float menggunakan pointer int berikut legal secara standar C99/C11?
    ```c
    float f = 10.0f;
    int *p = (int*)&f;
    *p = 0;
    ```
    *Kunci Jawaban:* **Ilegal.** Ini melanggar *Strict Aliasing Rule*. Kompilator berhak mengasumsikan pointer dari tipe `int*` tidak menunjuk ke lokasi memori yang sama dengan objek bertipe `float`, yang dapat menyebabkan *undefined behavior* saat optimasi agresif diaktifkan.

10. Jika kita memiliki struct dengan satu bit-field:
    ```c
    struct BitfieldSample {
        int val : 3;
    };
    ```
    Berapakah rentang nilai integer desimal yang dapat ditampung secara aman oleh `val`?
    *Kunci Jawaban:* Karena `int` bertanda (*signed*), bit-field 3 bita menggunakan representasi *Two's Complement*: bit tertinggi adalah bit tanda (*sign bit*). Rentang nilainya adalah dari $-2^{3-1}$ hingga $+2^{3-1} - 1$, yaitu **$-4$ hingga $+3$**. Menyimpan nilai `4` akan mengakibatkan *overflow/wrap-around* menjadi `-4`.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: In-Memory Key-Value Binary Storage Engine Record

#### Deskripsi
Buatlah sebuah modul C mandiri bernama `kv_record.c` dan `kv_record.h` yang merepresentasikan sebuah format *Database Record File* berbasis biner. Format ini mengimplementasikan konsep *Tagged Union*, *Memory Alignment*, dan *Flexible Array Member*.

#### Spesifikasi Fungsional:
1.  **Definisi Tipe Data:**
    *   Buat `enum DataType`: `TYPE_INT32`, `TYPE_DOUBLE`, `TYPE_STRING`.
    *   Buat `union ValueHolder` yang dapat menampung `int32_t`, `double`, atau representasi pointer string.
    *   Buat struktur `RecordHeader` yang dikemas rapi tanpa membuang memori:
        *   `uint32_t record_id`
        *   `uint16_t key_length`
        *   `uint8_t  type` (berasal dari `enum DataType`)
        *   `uint8_t  flags` (bit-field: `is_deleted : 1`, `is_compressed : 1`, `reserved : 6`)
2.  **Struktur Flexible Dynamic Record:**
    *   Buat `struct DBRecord`:
        *   `RecordHeader header;`
        *   `ValueHolder  value;`
        *   `char         key[];` (Flexible Array Member untuk menyimpan string kunci).
3.  **Fungsi yang Wajib Diimplementasikan:**
    *   `DBRecord* dbrecord_create(uint32_t id, const char *key, DataType type, ValueHolder val);`
        *   Mengalokasikan memori dinamis contiguous tunggal untuk struct beserta string `key` (termasuk karakter null-terminator).
        *   Memvalidasi integritas memori dan mencegah buffer overflow.
    *   `void dbrecord_print(const DBRecord *rec);`
        *   Mencetak seluruh metadata, offset memori masing-masing anggota menggunakan `offsetof`, dan nilai data sesuai tipenya.
    *   `void dbrecord_free(DBRecord *rec);`
        *   Membebaskan memori secara aman.

#### Kriteria Pengujian Verifikasi Mandiri:
*   Kompilasi kode Anda dengan flag ketat:
    ```bash
    gcc -std=c11 -Wall -Wextra -Werror -pedantic -g kv_record.c -o kv_record
    ```
*   Jalankan di bawah Valgrind untuk memastikan nol kebocoran memori (*0 memory leaks*) dan *no unaligned/invalid memory accesses*:
    ```bash
    valgrind --leak-check=full --show-leak-kinds=all ./kv_record
    ```
*   Bandingkan ukuran total struct dengan perhitungan manual Anda berdasarkan aturan kalkulasi alignment arsitektur target. Pastikan tidak ada fragmentasi memori yang tidak disengaja.