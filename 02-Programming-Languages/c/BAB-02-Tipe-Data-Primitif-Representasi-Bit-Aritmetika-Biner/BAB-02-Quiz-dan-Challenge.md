# BAB 02: Quiz, Challenge, & Knowledge Check
**Tipe Data Primitif, Representasi Bit, & Aritmetika Biner**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Mekanisme Two's Complement dan Eliminasi Dual-Zero
Jelaskan secara matematis dan representasi biner bagaimana sistem komplemen dua (*Two's Complement*) merepresentasikan bilangan bulat bertanda (*signed integers*). Bandingkan dengan sistem *Sign-and-Magnitude* dan *One's Complement*. Mengapa *Two's Complement* menjadi standar universal pada mikroprosesor modern dalam hal penyederhanaan sirkuit ALU (*Arithmetic Logic Unit*) dan eliminasi masalah *dual-zero*?

### Soal 1.2: Perbedaan Semantik Shift Aritmetika vs Logical
Jelaskan perbedaan mendasar antara *Logical Right Shift* (`>>>` pada beberapa bahasa tingkat tinggi, atau shift unsigned pada C) dan *Arithmetic Right Shift* (`>>` pada tipe bertanda). Apa bahaya laten menurut standar ISO/IEC 9899 (C Standard) sebelum C23 terkait melakukan operasi right-shift pada nilai *signed* bertanda negatif, dan mengapa hal tersebut dikategorikan sebagai *implementation-defined behavior*?

### Soal 1.3: Aturan Promosi Integer (Integer Promotion Rules)
Perhatikan potongan kode berikut:
```c
uint8_t a = 200;
uint8_t b = 100;
uint8_t c = (a + b) / 2;
```
Secara matematis $(200 + 100) / 2 = 150$, yang dapat ditampung dalam `uint8_t`. Namun, jelaskan urutan evaluasi tipe data internal (*implicit integer promotion*) yang terjadi pada ekspresi `(a + b)`. Apa tipe data hasil evaluasi parsial `a + b` di register CPU 32-bit/64-bit sebelum operasi pembagian, dan kapan *integer truncation* terjadi?

### Soal 1.4: Anatomi IEEE-754 Single-Precision dan Batasan Representasi
Bedah representasi 32-bit dari tipe data `float` standar IEEE-754 (alokasi bit Sign, Exponent dengan bias, dan Mantissa/Significand). Berdasarkan representasi tersebut, jelaskan mengapa ekspresi aritmetika `0.1f + 0.2f == 0.3f` bernilai *false*, dan definisikan konsep *Machine Epsilon* ($\epsilon$) dalam mitigasi komparasi bilangan mengambang.

### Soal 1.5: Portabilitas `stdint.h`: `int32_t`, `int_fast32_t`, dan `uintptr_t`
Mengapa *Senior Systems Engineer* menghindari penggunaan tipe data primitif telanjang seperti `long` atau `unsigned int` untuk struktur data biner persisten, dan lebih memilih `stdint.h`? Jelaskan perbedaan fungsional antara `int_exact` (seperti `int32_t`), `int_fast` (seperti `int_fast32_t`), dan `int_least` (seperti `int_least32_t`). Kapan Anda **wajib** menggunakan `uintptr_t` alih-alih `uint64_t` saat memanipulasi representasi numerik dari alamat memori?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Signed Overflow vs Unsigned Wrap-around dan Optimasi Kompiler
Dalam standar C, jelaskan konsekuensi hukum formal antara *unsigned integer wrap-around* (modulo $2^n$) versus *signed integer overflow* (*Undefined Behavior*). Bagaimana kompiler modern (seperti GCC/Clang dengan opsi optimasi `-O2` atau `-O3`) memanfaatkan status Undefined Behavior pada signed overflow untuk mengeliminasi kode pengecekan batas (misal: mengoptimasi loop `for (int i = 0; i <= i + 1; ++i)` menjadi *infinite loop* atau menghapus validasi `if (x + 100 < x)`)?

### Soal 2.2: Fenomena Subnormal/Denormal Numbers pada Real-Time DSP
Ketika nilai IEEE-754 mendekati nol hingga bit eksponen bernilai nol murni, angka tersebut beralih dari format *normalized* ke *denormalized/subnormal*. Jelaskan implikasi performa (*latency degradation*) ketika sirkuit FPU menangani subnormal numbers secara hardware/microcode trap. Mengapa sistem audio *real-time* atau DSP kritis sering kali menyalakan mode register FTZ (*Flush-to-Zero*) dan DAZ (*Denormals-are-Zero*)?

### Soal 2.3: Anti-Pattern Bit-Field untuk Binary Serialization
Mengapa kode berikut dianggap berbahaya dan dilarang keras dalam standar implementasi protokol jaringan (seperti TCP/IP stack) atau *driver device* lintas platform?
```c
struct HardwareRegister {
    uint32_t enable       : 1;
    uint32_t interrupt_en : 1;
    uint32_t mode         : 4;
    uint32_t reserved     : 26;
};
```
Jelaskan terkait ketergantungan urutan alokasi bit (*endianness of bit allocation within storage unit*), *padding*, *storage unit alignment*, dan ketiadaan portabilitas ABI lintas arsitektur CPU (x86 vs ARM vs RISC-V).

### Soal 2.4: Sign Extension Trap pada Operasi Bitwise dan Shift
Identifikasi *bug* fatal dan jelaskan *root cause* dari cuplikan kode 64-bit berikut:
```c
int32_t device_offset = -4; // 0xFFFFFFFC
uint64_t base_address = 0x80000000;
uint64_t target_address = base_address + (uint64_t)device_offset;
```
Mengapa nilai `target_address` tidak menghasilkan `0x7FFFFFFC`, melainkan alamat memori yang melonjak secara ekstrem? Bagaimana mekanisme *sign extension* bekerja ketika tipe bertanda dipromosikan ke ukuran bit yang lebih besar sebelum konversi tipe?

### Soal 2.5: Implementasi Portable Endianness Swap Tanpa Pelanggaran Strict Aliasing
Banyak pengembang melakukan konversi endianness menggunakan *pointer punning* seperti:
```c
uint32_t val = 0xAABBCCDD;
uint8_t *bytes = (uint8_t *)&val;
// menukar bytes[0] dengan bytes[3], dst.
```
Jelaskan mengapa pendekatan modifikasi in-place via pointer punning atau *type-punning union* dapat melanggar aturan optimasi *Strict Aliasing* dan *Pointer Alignment*. Tuliskan solusi murni berbasis bitwise operations (`<<`, `>>`, `&`, `|`) untuk membalik *endianness* sebuah 64-bit integer, dan jelaskan mengapa kompiler modern secara cerdas mengganti kode bitwise tersebut langsung menjadi instruksi assembly native atomik tunggal (seperti `BSWAP` pada x86 atau `REV` pada ARM).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Truncation dan Overflow pada Engine Matching Bursa Saham
*System Context*: Anda memimpin tim infrastruktur perdagangan frekuensi tinggi (*High-Frequency Trading* / HFT). Sistem bursa saham menggunakan format fixed-point 64-bit bertanda untuk menangani volume transaksi mikro-lot. Nilai tukar mata uang kripto dan transaksi saham dihitung dalam satuan mikro (skala $10^6$, di mana $1.000000$ USD direpresentasikan sebagai integer $1\,000\,000$).
*Insiden*: Pada kondisi pasar ekstrem (*flash crash*), terjadi lonjakan pesanan dengan volume besar. Mesin eksekusi tiba-tiba mencatatkan transaksi bernilai negatif triliunan rupiah dan mengeksekusi *margin call* yang salah secara massal, mengakibatkan suspensi perdagangan. Kode yang dicurigai:
```c
int64_t calculate_total_micro_units(int32_t unit_price, int32_t quantity) {
    // unit_price dan quantity menggunakan skala mikro (10^6)
    // Formula dasar: (price * quantity) / 10^6
    int64_t total = (unit_price * quantity) / 1000000L;
    return total;
}
```
* **Pertanyaan Diagnostik**:
  1. Identifikasi lokasi tepat terjadinya *integer overflow* dan jelaskan mengapa penetapan tipe kembalian `int64_t` tidak mencegah terjadinya kalkulasi salah pada ekspresi di sisi kanan tanda sama dengan.
  2. Jelaskan urutan tipe data (*type promotion*) pada `unit_price * quantity`. Mengapa penambahan literal `1000000L` terlambat menyelamatkan presisi kalkulasi?
  3. Berikan refaktorisasi kode yang aman dari *undefined behavior*, efisien secara komputasi CPU cycles (tanpa alokasi floating point), serta mampu mendeteksi potensi overflow sebelum eksekusi dilakukan.

---

### Skenario B: Kerusakan Data Multithreaded Akibat Bit-Field Non-Atomic Storage Units
*System Context*: Anda menangani firmware untuk Electronic Control Unit (ECU) otomotif berbasis multi-core ARM Cortex-R. Di dalam memori bersama (*shared memory*), terdapat status telemetri kendaraan yang dikemas dalam *bit-field struct* guna menghemat alokasi cache L1:
```c
typedef struct {
    uint32_t brake_applied   : 1;  // Dimutasi oleh Core 0 (Sistem Pengereman)
    uint32_t cruise_active   : 1;  // Dimutasi oleh Core 1 (Sistem Navigasi)
    uint32_t current_speed   : 10; // Dimutasi oleh Core 0
    uint32_t engine_temp     : 10; // Dimutasi oleh Core 1
    uint32_t error_code      : 10;
} VehicleStatus;

volatile VehicleStatus g_status;
```
*Insiden*: Di lintasan uji coba, aktivasi mendadak pada *cruise control* oleh Core 1 sesekali menyebabkan status `brake_applied` yang ditulis oleh Core 0 ter-reset secara acak ke nol, menyebabkan kendaraan gagal melakukan deselerasi darurat. Analisis perangkat keras membuktikan tidak ada kerusakan kabel atau sensor fisik.
* **Pertanyaan Diagnostik**:
  1. Bedah bagaimana CPU mengeksekusi operasi tulis pada level instruksi mesin (*load-modify-store cycle*) terhadap variabel bit-field di atas. Mengapa bit-field **bukan** unit independen pada level bus memori?
  2. Jelaskan konsep *Memory Storage Unit Allocation*. Mengapa Core 0 dan Core 1 mengalami *race condition* (Data Race) meskipun mereka secara logika memodifikasi variabel anggota *struct* yang berbeda?
  3. Bagaimana strategi restrukturisasi data biner ini tanpa membuang efisiensi ruang? Bandingkan solusi menggunakan *Atomic Bitwise Operations* (`stdatomic.h` atau GCC built-in atomic) terhadap pemisahan alokasi *byte boundary alignment*.

---

### Skenario C: Kegagalan Parsing Paket Telemetri Satelit Akibat Endianness dan Padding
*System Context*: Sistem transmisi darat (*Ground Segment*) menerima paket telemetri biner langsung dari modul mikro-satelit orbit rendah (LEO). Modul mikrokontroler satelit berbasis mikroarsitektur Big-Endian (misal: RISC-V 32-bit big-endian profile), sedangkan server pengolah data darat menggunakan prosesor AMD EPYC berbasis Little-Endian (x86-64).
Data yang ditransmisikan mentah (*raw byte payload*) sebesar 10 byte memiliki struktur biner:
* Byte 0: Sync Marker (`0xAA`)
* Byte 1-2: Sensor Voltage (16-bit unsigned integer, raw value)
* Byte 3-6: Timestamp (32-bit unsigned integer, epoch ms)
* Byte 7-8: Radiation Level (16-bit signed integer)
* Byte 9: Checksum (8-bit XOR)

Seorang insinyur junior menulis kode di server darat:
```c
#pragma pack(push, 1)
typedef struct {
    uint8_t  sync;
    uint16_t voltage;
    uint32_t timestamp;
    int16_t  radiation;
    uint8_t  checksum;
} TelemetryPacket;
#pragma pack(pop)

void process_packet(const uint8_t *buffer) {
    const TelemetryPacket *pkt = (const TelemetryPacket *)buffer;
    if (pkt->voltage > 3300) {
        trigger_overvoltage_alarm();
    }
}
```
*Insiden*: Server darat terus-menerus memicu `trigger_overvoltage_alarm()` dan mencatat timestamp tahun 2085, meskipun satelit beroperasi normal.
* **Pertanyaan Diagnostik**:
  1. Analisis bagaimana angka `voltage = 3.3V` (direpresentasikan sebagai `0x0CE4` atau `3300`) dibaca oleh arsitektur little-endian saat dipetakan secara direct pointer casting. Nilai desimal riil berapa yang dilihat oleh instruksi perbandingan?
  2. Jelaskan bahaya penggunaan `#pragma pack(1)` pada arsitektur tertentu (seperti ARM versi lama atau MIPS) terkait *unaligned memory access trap* (SIGBUS) vs penalti performa emulasi via exception handler kernel.
  3. Tuliskan pola decoding paket telemetri biner yang terbebas dari *direct memory casting*, kebal terhadap variasi *endianness*, serta aman dari *unaligned memory access fault*.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Endian-Safe Bit-Packed Telemetry Frame Decoder

#### Problem Statement
Dalam protokol komunikasi drone otonom, efisiensi bandwidth transmisi radio sangat krusial. Telemetri dikirimkan dalam format biner terpadatkan (*densely packed non-byte-aligned bits*). Setiap frame telemetri terdiri dari ** persis 5 byte (40 bit)** payload yang dikirim secara *Big-Endian network order*, tanpa padding byte di antara setiap komponen field.

Struktur 40-bit data tersebut didefinisikan sebagai berikut:
* **Field 1 (Bits 0-3 / 4 bit)**: Frame Type (Unsigned, bit 0 adalah MSB dari frame).
* **Field 2 (Bits 4-15 / 12 bit)**: Battery Millivolts (Unsigned, rentang nilai 0 - 4095 mV).
* **Field 3 (Bits 16-25 / 10 bit)**: Pitch Angle (Signed integer komplemen dua, rentang -512 s/d +511 derajat dengan resolusi 1 derajat).
* **Field 4 (Bits 26-38 / 13 bit)**: Altitude (Fixed-point unsigned, 11 bit integer, 2 bit fractional: format Q11.2, resolusi 0.25 meter).
* **Field 5 (Bit 39 / 1 bit)**: Fail-Safe Status (Flag boolean, 1 = Triggered, 0 = Normal).

#### Requirements
1. Buat fungsi C murni dengan tanda tangan (*signature*):
   ```c
   typedef struct {
       uint8_t  frame_type;       // Nilai 0 - 15
       uint16_t battery_mv;       // Nilai 0 - 4095
       int16_t  pitch_deg;        // Nilai -512 s/d +511 (Signed Sign-Extended!)
       float    altitude_m;       // Konversi akurat dari Q11.2 (misal: 5.75 m)
       bool     failsafe_active;  // true / false
   } ParsedTelemetry;

   bool parse_telemetry_frame(const uint8_t raw_stream[5], ParsedTelemetry *out_data);
   ```
2. **Karakteristik Wajib Implementasi**:
   * **Bit Manipulation Purity**: Dilarang keras memetakan bit menggunakan C `struct bit-fields` guna mencegah *implementation-defined behavior*. Gunakan pergeseran bit (*bitwise shift*), *masking*, dan manipulasi integer murni.
   * **Sign Extension Correctness**: Field `pitch_deg` bernilai 10-bit signed. Anda **harus** melakukan proses rekonstruksi komplemen dua secara benar menjadi `int16_t` standar C (jika bit tanda ke-9 bernilai 1, nilai harus terpropagasi negatif secara tepat pada tipe `int16_t`).
   * **Fixed-Point Conversion**: Konversikan data altitude Q11.2 menjadi `float` tanpa kehilangan presisi pecahan (pembagi desimal `4.0f`).
   * **Zero Dynamic Allocation & Zero Library Overhead**: Fungsi tidak boleh menggunakan `malloc`, `printf`, `memcpy`, atau dependensi sistem lain.

#### Constraints
* **Platform Invariance**: Kode harus menghasilkan output identik baik dikompilasi pada arsitektur Little-Endian (x86_64, AArch64) maupun Big-Endian.
* **Safety**: Input pointer `raw_stream` dan `out_data` harus diverifikasi non-null (kembalikan `false` jika invalid).
* **Memory Safety**: Bebas dari perilaku *Undefined Behavior* (UB), termasuk tidak ada pemanfaatan left-shift pada tipe data signed negatif atau shift melewati lebar bit tipe data.

#### Expected Output Test Vectors
Jika diberikan input raw hex array:
`uint8_t raw_data[5] = { 0x9B, 0x8C, 0xF9, 0xC4, 0x01 };`

Lakukan trace manual / program kalkulasi bit:
1. `0x9` (4-bit awal): Frame Type = `9`
2. Ekstraksi 12-bit Battery: `0xB8C` = `2956` mV
3. Ekstraksi 10-bit Pitch: Rekonstruksi bitwise dan sign-extension untuk mendapatkan nilai negatif atau positif yang tepat.
4. Ekstraksi 13-bit Altitude: Nilai mentah integer di-cast ke representasi desimal `(raw_val * 0.25f)`.
5. Ekstraksi 1-bit Failsafe: Nilai boolean terisolasi.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk audit mandiri penguasaan materi Bab 02 sebelum melangkah ke Bab 03 (*Pointers, Memory Layout, dan Virtual Memory Architecture*).

### Saya harus memahami:
- [ ] Representasi data komplemen dua (*Two's Complement*), batas nilai minimum dan maksimum ($[-2^{n-1}, 2^{n-1}-1]$), dan alasan matematis mengapa batas bawah memiliki rentang 1 digit lebih banyak dibanding batas atas.
- [ ] Aturan *Integer Promotion* dan bahaya komparasi campuran antara `signed` dan `unsigned` (mengapa `-1 > 1U` bernilai `true`).
- [ ] Format IEEE-754: Definisi bit Sign, Biased Exponent, Mantissa implisit (*hidden bit*), serta batas antara bilangan *Normalized*, *Subnormal*, *Infinity*, dan *NaN*.
- [ ] Perbedaan esensial perlakuan standar C terhadap *Signed Overflow* (Undefined Behavior) versus *Unsigned Overflow* (Well-defined modulo wrap-around).
- [ ] Konsep *Endianness* (Big-Endian vs Little-Endian) pada representasi byte memori dan mengapa shift bitwise (`<<`, `>>`) secara semantik independen terhadap endianness arsitektur CPU.
- [ ] Keterbatasan dan kelemahan *C Bit-fields* untuk pemetaan hardware atau protokol jaringan biner.
- [ ] Mekanisme propagasi bit pada *Sign Extension* saat memperluas ukuran bit data bertanda (*narrow to wide casting*).

### Saya tidak perlu menghafal:
- [ ] Nilai eksak hexadesimal dari batas eksponen IEEE-754 (cukup pahami formula bias $2^{e-1}-1$).
- [ ] Urutan presisi implementasi compiler-specific untuk bitfield layout internal.
- [ ] Nilai desimal presisi tinggi dari representasi IEEE-754 mantissa (misal: 0.1 dalam biner tak hingga).
- [ ] Rincian implementasi assembly internal instruksi spesifik CPU untuk swapping bytes (cukup pahami instruksi logisnya, biarkan optimasi kompiler memetakan ke `BSWAP`, `REV`, dsb.).

### Saya harus bisa melakukan:
- [ ] Menulis operasi manipulasi bit tingkat rendah (*masking*, *setting*, *clearing*, *toggling*, *extracting*) menggunakan kombinasi operator bitwise murni (`&`, `|`, `^`, `~`, `<<`, `>>`).
- [ ] Menerapkan *manual sign-extension* pada integer kustom sembarang bit-width (misal: memperluas signed 10-bit atau 24-bit ke 32-bit integer).
- [ ] Mengonversi format *fixed-point arithmetic* (Q-format) ke floating point dan sebaliknya menggunakan operasi aritmetika integer murni.
- [ ] Menulis fungsi serialisasi dan deserialisasi data biner lintas arsitektur (*endian-agnostic decoder/encoder*) yang kebal terhadap *strict-aliasing rule* dan *memory alignment issues*.
- [ ] Menganalisis dan memperbaiki bug produksi yang dipicu oleh konversi tipe implisit (*implicit casting bug*), *integer truncation*, dan *signed integer overflow*.