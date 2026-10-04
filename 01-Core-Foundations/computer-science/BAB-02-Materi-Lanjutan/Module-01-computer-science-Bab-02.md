## SEKSI 01 — IDENTITAS MODUL

*   **Modul ID:** `CS-CORE-02-01`
*   **Kategori:** `01-Core-Foundations`
*   **Mata Kuliah / Jalur:** Computer Science Core / Computer Systems Architecture
*   **Bab 02:** Arsitektur Komputer & Sistem Digital
*   **Modul 01:** Fondasi Sistem Digital: Dari Gerbang Logika, Logika Sekuensial, hingga Eksekusi Von Neumann
*   **Prasyarat Akademis:** Logika Matematika Diskrit Dasar, Representasi Bilangan Biner/Heksadesimal, Dasar Pemrograman Imperatif (C/Rust disarankan).
*   **Target Audiens:** Mahasiswa Ilmu Komputer tingkat dasar/menengah, Software Engineer yang ingin mendalami *hardware-software interface*, dan Systems Programmer.
*   **Alokasi Waktu:** 8 Jam Teori Mandiri, 6 Jam Praktikum/Implementasi.
*   **Toolkit & Lingkungan:** Logisim-Evolution, GCC/Clang (C99+), Python 3.10+ (untuk scripting verifikasi bitwise).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara komprehensif, pembelajar mampu:

1.  **Menganalisis dan Menyederhanakan** fungsi Boolean menggunakan Aljabar Boolean dan Karnaugh Maps (K-Maps) hingga mencapai bentuk *Sum of Products* (SOP) dan *Product of Sums* (POS) yang minimal.
2.  **Merancang Sirkuit Kombinasional** fundamental (Multiplexer, Demultiplexer, Decoder, Half Adder, Full Adder, dan Arithmetic Logic Unit 4-bit) dengan batasan gerbang universal (NAND/NOR).
3.  **Membedakan Perilaku Temporal** antara elemen penyimpan asinkron (*Latch*) dan sinkron (*Edge-Triggered Flip-Flop*), serta menghitung batasan waktu kritis (*setup time*, *hold time*, dan *propagation delay*).
4.  **Membangun Finite State Machine (FSM)** sinkron tipe Mealy dan Moore untuk pengendali logika berurutan (*Sequential Control Logic*).
5.  **Mendekonstruksi Paradigma Von Neumann**, menjelaskan interaksi antara Datapath, Control Unit, Subsistem Memori, dan Antarmuka Bus I/O selama siklus *Fetch-Decode-Execute*.
6.  **Mengimplementasikan Emulator CPU Minimalis** berbasis perangkat lunak untuk mengeksekusi instruksi dasar tingkat mesin secara deterministik.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
Level 0: Fisika Semikonduktor
   │
   ▼
Level 1: Transistor Switching (CMOS: NMOS & PMOS)
   │
   ▼
Level 2: Gerbang Logika Dasar & Universal (NOT, AND, OR, XOR, NAND, NOR)
   │
   ├─────────────────────────────────────────┐
   ▼                                         ▼
Level 3A: Logika Kombinasional            Level 3B: Logika Sekuensial
(State-less, Output = f(Input))           (State-dependent, Output = f(Input, State))
   ├─ Adders (Half/Full Adder, CLA)          ├─ Latches (SR, D-Latch)
   ├─ Multiplexer & Demultiplexer            ├─ Flip-Flops (D, JK, T Edge-Triggered)
   ├─ Decoders & Encoders                    ├─ Registers & Shift Registers
   └─ Arithmetic Logic Unit (ALU)            └─ Counters & Finite State Machines (FSM)
   │                                         │
   └────────────────────┬────────────────────┘
                        │
                        ▼
Level 4: Datapath & Microarchitecture
   │
   ├─ Register File (RF)
   ├─ Arithmetic Logic Unit (ALU Integration)
   ├─ Program Counter (PC) & Instruction Register (IR)
   └─ Control Unit (Hardwired / Microcoded)
                        │
                        ▼
Level 5: Model Mesin Von Neumann
   ├─ Memori Terpadu (Data & Program)
   ├─ System Bus (Address, Data, Control Bus)
   └─ Siklus Eksekusi (Fetch -> Decode -> Execute -> Writeback)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sistem perangkat lunak modern dibangun di atas lapisan abstraksi yang masif: dari kernel sistem operasi, runtime bahasa, hingga mesin virtual dan compiler tingkat tinggi. Namun, abstraksi ini bocor (*abstraction leakage*). Menulis kode berkinerja tinggi, aman, dan efisien secara energi mustahil dilakukan tanpa memahami batasan fisik perangkat keras:

1.  **Eksploitasi Kinerja Tingkat Mesin:** Operasi bitwise tingkat rendah, optimasi *branch prediction*, struktur algoritma bebas percabangan (*branchless programming*), dan penyelarasan memori (*memory alignment*) berakar langsung pada cara sirkuit digital dan jalur data (datapath) mengeksekusi bit.
2.  **Mitigasi Kerentanan Keamanan Perangkat Keras:** Kerentanan kelas arsitektural seperti *Meltdown*, *Spectre*, serta kondisi balapan (*race condition*) tingkat gerbang (glitch) hanya dapat dimitigasi oleh insinyur yang memahami interaksi siklus jam, pipeline, dan register.
3.  **Rekayasa Sistem Tertanam & Akselerator Kustom:** Pengembangan sistem berbasis FPGA, ASIC, driver perangkat keras, maupun akselerator machine learning (seperti NPU dan TPU) menuntut perancangan sirkuit kombinasional serta sekuensial yang efisien dari segi silikon dan konsumsi daya.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Aljabar Boolean dan Gerbang Logika
Sistem digital merepresentasikan informasi dalam tegangan diskret: logika biner `0` (rendah/GND) dan `1` (tinggi/$V_{DD}$). Operasi digital diformalkan melalui Aljabar Boolean dengan aksioma penutupan (*closure*), komutatif, asosiatif, distributif, identitas, dan komplemen.

Hukum De Morgan menjadi pilar transformasi sirkuit:
$$\overline{A \cdot B} = \bar{A} + \bar{B}$$
$$\overline{A + B} = \bar{A} \cdot \bar{B}$$

Gerbang **NAND** dan **NOR** diklasifikasikan sebagai *gerbang universal*, karena kombinasi fungsional dari salah satu gerbang ini dapat mengonstruksi operasi logika Boolean apa pun (NOT, AND, OR, XOR).

### 2. Logika Kombinasional vs. Logika Sekuensial
*   **Logika Kombinasional:** Output pada waktu $t$ murni merupakan fungsi dari input pada waktu $t$. Sirkuit ini tidak memiliki memori internal. Contoh: Adder, Multiplexer (MUX), Arithmetic Logic Unit (ALU).
*   **Logika Sekuensial:** Output bergantung pada input saat ini dan riwayat input sebelumnya (*state*). Membutuhkan elemen memori dan umumnya disinkronkan oleh pulsa periodik yang disebut sinyal detak (*clock*).

### 3. Arsitektur Von Neumann
Diusulkan oleh John von Neumann pada tahun 1945, arsitektur ini mendefinisikan sistem komputasi tujuan umum dengan karakteristik utama:
*   **Stored-Program Concept:** Data dan instruksi program berbagi ruang memori fisik yang sama serta diakses melalui jalur bus yang sama.
*   **Komponen Inti:**
    *   *Central Processing Unit (CPU)* yang terdiri atas *Control Unit* (CU) dan *Arithmetic Logic Unit* (ALU), serta register internal.
    *   *Subsistem Memori Utama (RAM)* untuk menyimpan data dan instruksi.
    *   *Mekanisme Input/Output (I/O)*.
    *   *Bus Antar-komponen* (Address Bus, Data Bus, Control Bus).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Mekanisme 1: Sintesis Logika Kombinasional (Full Adder)
Full Adder menerima tiga input 1-bit: $A$, $B$, dan Carry-In ($C_{in}$), serta menghasilkan dua output 1-bit: Sum ($S$) dan Carry-Out ($C_{out}$).

Tabel Kebenaran (*Truth Table*):
| $A$ | $B$ | $C_{in}$ | $S$ | $C_{out}$ |
|:---:|:---:|:--------:|:---:|:---------:|
|  0  |  0  |    0     |  0  |     0     |
|  0  |  0  |    1     |  1  |     0     |
|  0  |  1  |    0     |  1  |     0     |
|  0  |  1  |    1     |  0  |     1     |
|  1  |  0  |    0     |  1  |     0     |
|  1  |  0  |    1     |  0  |     1     |
|  1  |  1  |    0     |  0  |     1     |
|  1  |  1  |    1     |  1  |     1     |

Ekspresi Boolean teroptimasi:
$$S = A \oplus B \oplus C_{in}$$
$$C_{out} = (A \cdot B) + (C_{in} \cdot (A \oplus B))$$

### Mekanisme 2: Elemen Penyimpan Data (D-Type Flip-Flop)
Untuk mencegah transparansi latch di mana perubahan input langsung merambat ke output selama level clock aktif, sistem sekuensial modern menggunakan **Edge-Triggered D-Flip-Flop** (umumnya dirancang menggunakan topologi Master-Slave).

```text
               MASTER (Latch)                    SLAVE (Latch)
           ┌──────────────────────┐          ┌──────────────────────┐
    D ────►│ D                  Q ├─────────►│ D                  Q ├────► Q
           │                      │          │                      │
CLK ──┬───►│ CLK                  │    ┌────►│ CLK                  │
      │    └──────────────────────┘    │     └──────────────────────┘
     [NOT]                             │
      └────────────────────────────────┘
```
1.  Saat $CLK = 0$: Master aktif (transparan terhadap $D$), Slave tidak aktif (mengisolasi output $Q$, mempertahankan nilai lama).
2.  Saat transisi $0 \to 1$ (*rising edge*): Master terkunci (mengisolasi input $D$), Slave aktif (meneruskan nilai Master ke output $Q$).
3.  Hasilnya: Nilai $D$ disampel secara presisi hanya pada saat transisi tepi sinyal detak.

### Mekanisme 3: Siklus Eksekusi Mesin Von Neumann
CPU mengeksekusi instruksi melalui urutan *micro-operations* yang berulang:

```text
 ┌─────────┐      ┌──────────┐      ┌─────────┐      ┌───────────┐
 │  FETCH  ├─────►│  DECODE  ├─────►│ EXECUTE ├─────►│ WRITEBACK │
 └────▲────┘      └──────────┘      └─────────┘      └─────┬─────┘
      │                                                    │
      └────────────────────────────────────────────────────┘
```

1.  **Fetch:**
    *   Isi register `Program Counter` (PC) diletakkan ke *Memory Address Bus*.
    *   Control Unit mengirim sinyal `Memory Read`.
    *   Instruksi dibaca dari RAM melalui *Data Bus* dan dimuat ke `Instruction Register` (IR).
    *   PC diinkrementasi: $PC \leftarrow PC + \text{panjang\_instruksi}$.
2.  **Decode:**
    *   Control Unit mem-parsing opcode dari IR.
    *   Mengidentifikasi mode pengalamatan dan membaca operan dari register internal atau menghitung alamat memori efektif.
3.  **Execute:**
    *   ALU melakukan operasi aritmatika/logika sesuai kendali sinyal dari Control Unit.
    *   Jika terdapat instruksi pencabangan (*branch/jump*), nilai PC dievaluasi ulang berdasarkan kondisi flag (Zero, Carry, Negative, Overflow).
4.  **Writeback:**
    *   Hasil eksekusi ditulis kembali ke register tujuan (*Register File*) atau ke memori utama melalui operasi `Memory Write`.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah arsitektur mikro prosesor sederhana 4-bit/8-bit berbasis model Von Neumann yang mengintegrasikan Datapath dan Control Unit:

```text
+===================================================================================+
|                               CENTRAL PROCESSING UNIT                             |
|                                                                                   |
|  +------------------------- CONTROL UNIT (CU) ---------------------------------+  |
|  | Sinyal Kontrol: [RegWrite, ALUOp, MemRead, MemWrite, Branch, ALUSrc]        |  |
|  +------------------------------------▲----------------------------------------+  |
|                                       | (Opcode)                                  |
|  +------------------------------------+----------------------------------------+  |
|  |                               DATAPATH                                      |  |
|  |                                                                             |  |
|  |  +--------------------+             +------------------------------------+  |  |
|  |  |   Program Counter  |             |           REGISTER FILE            |  |  |
|  |  |        (PC)        |             |  +-----+-----+-----+-----+         |  |  |
|  |  +---------┬----------+             |  | R0  | R1  | R2  | R3  |         |  |  |
|  |            │                        |  +-----+-----+-----+-----+         |  |  |
|  |            │                        +-----▲----------┬--------┬----------+  |  |
|  |            │                              │          │        │             |  |
|  |            │                              │ Write    │ Read 1 │ Read 2      |  |
|  |            │                              │ Data     │ Operan │ Operan      |  |
|  |            │                              │          │        │             |  |
|  |            │                              │          ▼        ▼             |  |
|  |            │                              │        +------------+           |  |
|  |            │                              │        | Multiplexer|           |  |
|  |            │                              │        +-----┬------+           |  |
|  |            │                              │              │                  |  |
|  |            │                              │              ▼                  |  |
|  |            │                              │       +--------------+          |  |
|  |            │                              │       |     ALU      |          |  |
|  |            │                              │       | (Arithmetic  |          |  |
|  |            │                              │       | Logic Unit)  |          |  |
|  |            │                              │       +------┬-------+          |  |
|  |            │                              │              │                  |  |
|  |            │ (Alamat Instruksi)           │              │ Flags (Z, C, V)  |  |
|  |            │                              │              ▼                  |  |
|  |            │              Result Bus      │       +--------------+          |  |
|  |            │    ┌─────────────────────────┴───────┤ ALU Out Reg  |          |  |
|  |            │    │                                 +--------------+          |  |
|  +------------┼────┼───────────────────────────────────────────────────────────+  |
+===============│====│===============================================================+
                │    │
       +--------▼----▼------------------------------------------------+
       |                         SYSTEM BUS                           |
       |  - Address Bus [A0..An]                                      |
       |  - Data Bus    [D0..Dn]                                      |
       |  - Control Bus [RD, WR, M/IO, CLK]                           |
       +------------------------------┬────────────────---------------+
                                      │
                                      ▼
       +--------------------------------------------------------------+
       |                  SUBSISTEM MEMORI UTAMA                      |
       |  (Menyimpan Program/Instruksi DAN Data Runtime Bersama-sama) |
       |                                                              |
       |  0x0000: [Instruksi: LOAD R1, [0x00FF]]                      |
       |  0x0001: [Instruksi: ADD  R1, R2      ]                      |
       |  ...                                                         |
       |  0x00FF: [Data: 0x4A                  ]                      |
       +--------------------------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Implementasi konseptual gerbang logika dasar menggunakan operator bitwise dalam C. Contoh ini mendemonstrasikan bagaimana fungsi kombinasional murni (Half Adder) dibentuk dari operator primitif:

```c
#include <stdio.h>
#include <stdint.h>

typedef struct {
    uint8_t sum;
    uint8_t carry;
} HalfAdderResult;

/**
 * Merepresentasikan sirkuit Half Adder 1-bit.
 * Logika Boolean:
 * Sum   = A ^ B   (XOR)
 * Carry = A & B   (AND)
 */
HalfAdderResult half_adder(uint8_t a, uint8_t b) {
    HalfAdderResult out;
    // Sanitasi input agar validitas 1-bit terjaga
    a = a & 0x01;
    b = b & 0x01;

    out.sum   = a ^ b;
    out.carry = a & b;
    return out;
}

int main(void) {
    printf("A | B | Sum | Carry\n");
    printf("--+---+-----+------\n");
    for (uint8_t a = 0; a <= 1; ++a) {
        for (uint8_t b = 0; b <= 1; ++b) {
            HalfAdderResult res = half_adder(a, b);
            printf("%u | %u |  %u  |   %u\n", a, b, res.sum, res.carry);
        }
    }
    return 0;
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah implementasi lengkap perangkat lunak berbasis C99 untuk sebuah **CPU Von Neumann 8-bit Virtual (The TinyVM-8)**. Mesin ini memiliki memori 256-byte terpadu (menyimpan kode dan data), 1 Register Akumulator ($AC$), Program Counter ($PC$), dan mengeksekusi siklus *Fetch-Decode-Execute*.

```c
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>

#define MEMORY_SIZE 256

/* Set Instruksi Opcodes */
typedef enum {
    OP_HALT = 0x00, // Berhenti
    OP_LOAD = 0x01, // AC = Memory[addr]
    OP_STORE= 0x02, // Memory[addr] = AC
    OP_ADD  = 0x03, // AC = AC + Memory[addr]
    OP_SUB  = 0x04, // AC = AC - Memory[addr]
    OP_JNZ  = 0x05, // Jump to addr if AC != 0
    OP_NOP  = 0x06  // No operation
} Opcode;

/* Struktur State CPU Von Neumann */
typedef struct {
    uint8_t ac;           // Accumulator Register
    uint8_t pc;           // Program Counter
    uint8_t ir;           // Instruction Register
    uint8_t mar;          // Memory Address Register
    uint8_t mdr;          // Memory Data Register
    bool    zero_flag;    // Status Flag Z
    bool    halted;       // Status Operasional
    uint8_t memory[MEMORY_SIZE]; // Memori terpadu Von Neumann
} VonNeumannMachine;

void cpu_init(VonNeumannMachine *cpu) {
    cpu->ac = 0;
    cpu->pc = 0;
    cpu->ir = 0;
    cpu->mar = 0;
    cpu->mdr = 0;
    cpu->zero_flag = false;
    cpu->halted = false;
    for (size_t i = 0; i < MEMORY_SIZE; ++i) {
        cpu->memory[i] = 0;
    }
}

void cpu_step(VonNeumannMachine *cpu) {
    if (cpu->halted) return;

    /* 1. FETCH PHASE */
    cpu->mar = cpu->pc;
    cpu->mdr = cpu->memory[cpu->mar];
    cpu->ir = cpu->mdr;
    cpu->pc++;

    /* 2. DECODE & EXECUTE PHASE */
    switch (cpu->ir) {
        case OP_HALT:
            cpu->halted = true;
            break;

        case OP_LOAD:
            // Fetch operan alamat (byte berikutnya)
            cpu->mar = cpu->pc++;
            cpu->mar = cpu->memory[cpu->mar]; // Dereferensi pointer argumen
            cpu->ac  = cpu->memory[cpu->mar]; // Muat data ke AC
            cpu->zero_flag = (cpu->ac == 0);
            break;

        case OP_STORE:
            cpu->mar = cpu->pc++;
            cpu->mar = cpu->memory[cpu->mar];
            cpu->memory[cpu->mar] = cpu->ac;  // Tulis AC ke RAM
            break;

        case OP_ADD:
            cpu->mar = cpu->pc++;
            cpu->mar = cpu->memory[cpu->mar];
            cpu->ac += cpu->memory[cpu->mar]; // Operasi ALU
            cpu->zero_flag = (cpu->ac == 0);
            break;

        case OP_SUB:
            cpu->mar = cpu->pc++;
            cpu->mar = cpu->memory[cpu->mar];
            cpu->ac -= cpu->memory[cpu->mar];
            cpu->zero_flag = (cpu->ac == 0);
            break;

        case OP_JNZ:
            cpu->mar = cpu->pc++;
            uint8_t target_addr = cpu->memory[cpu->mar];
            if (!cpu->zero_flag) {
                cpu->pc = target_addr;        // Modifikasi aliran eksekusi
            }
            break;

        case OP_NOP:
            break;

        default:
            fprintf(stderr, "Illegal Instruction 0x%02X encountered at PC: 0x%02X\n",
                    cpu->ir, (uint8_t)(cpu->pc - 1));
            cpu->halted = true;
            break;
    }
}

int main(void) {
    VonNeumannMachine cpu;
    cpu_init(&cpu);

    /* 
     * Program: Menghitung Perkalian dengan Penjumlahan Berulang
     * Komputasi: 3 * 4 = 12
     *
     * Alokasi Variabel di Memori Data:
     * [0x20] = Multiplicand (3)
     * [0x21] = Counter/Multiplier (4)
     * [0x22] = Decrement Constant (1)
     * [0x23] = Result (Akumulasi akhir)
     */
    cpu.memory[0x20] = 3;
    cpu.memory[0x21] = 4;
    cpu.memory[0x22] = 1;
    cpu.memory[0x23] = 0;

    /* Kode Mesin di Ruang Memori Program (Mulai 0x00) */
    uint8_t program[] = {
        // LOOP_START (0x00):
        OP_LOAD,  0x21, // 0x00: Load Counter ke AC
        OP_SUB,   0x22, // 0x02: AC = AC - 1
        OP_STORE, 0x21, // 0x04: Simpan kembali Counter baru
        
        OP_LOAD,  0x23, // 0x06: Load Result ke AC
        OP_ADD,   0x20, // 0x08: AC = AC + Multiplicand
        OP_STORE, 0x23, // 0x0A: Simpan Result

        OP_LOAD,  0x21, // 0x0C: Load Counter untuk evaluasi Zero Flag
        OP_JNZ,   0x00, // 0x0E: Jika Counter != 0, loncat ke LOOP_START (0x00)

        OP_HALT         // 0x10: Selesai
    };

    for (size_t i = 0; i < sizeof(program); ++i) {
        cpu.memory[i] = program[i];
    }

    printf("[EMULASI DIMULAI]\n");
    uint32_t cycle_count = 0;
    while (!cpu.halted) {
        cpu_step(&cpu);
        cycle_count++;
    }

    printf("Emulasi selesai dalam %u siklus instruksi.\n", cycle_count);
    printf("Hasil di Memori [0x23]: %u (Ekspektasi: 12)\n", cpu.memory[0x23]);
    printf("Status Akhir CPU: PC=0x%02X, AC=0x%02X, ZeroFlag=%d\n",
           cpu.pc, cpu.ac, cpu.zero_flag);

    return 0;
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Dalam desain sistem digital dan mikroarsitektur, insinyur terus-menerus mengelola pertukaran parameter (*trade-offs*):

### 1. Ripple Carry Adder (RCA) vs. Carry-Lookahead Adder (CLA)
*   **Ripple Carry Adder:**
    *   *Kelebihan:* Kompleksitas sirkuit rendah ($O(n)$ gerbang logika), area silikon kecil, routing interkoneksi sederhana.
    *   *Kekurangan:* Keterlambatan perambatan (*propagation delay*) tinggi ($O(n)$) karena bit carry harus merambat dari bit ke-0 hingga bit ke-$n$.
*   **Carry-Lookahead Adder:**
    *   *Kelebihan:* Sangat cepat ($O(\log n)$ waktu propagasi) karena carry dihitung secara simultan menggunakan logika generate ($G_i = A_i \cdot B_i$) dan propagate ($P_i = A_i \oplus B_i$).
    *   *Kekurangan:* Konsumsi area silikon besar ($O(n \log n)$), fan-in gerbang meningkat tajam, konsumsi daya dinamis tinggi.

### 2. Von Neumann vs. Harvard Architecture
*   **Von Neumann:**
    *   *Kelebihan:* Efisiensi alokasi memori (program dan data memperebutkan kapasitas yang sama secara fleksibel), subsistem bus tunggal menekan biaya pin IC.
    *   *Kekurangan:* **Von Neumann Bottleneck**—kecepatan eksekusi CPU dibatasi oleh bandwidth transfer instruksi dan data pada bus bersama.
*   **Harvard (atau Modified Harvard pada CPU Modern):**
    *   *Kelebihan:* Akses instruksi dan data berlangsung secara independen dan simultan dalam satu siklus jam (memori instruksi dan data terpisah). Menghilangkan bottleneck bus dasar.
    *   *Kekurangan:* Inefisiensi fragmentasi memori (ruang instruksi yang kosong tidak dapat dipakai oleh data runtime tanpa sirkuit translasi khusus), interkoneksi bus lebih mahal.

### 3. Batasan Waktu: Latensi vs. Frekuensi Clock
Menaikkan frekuensi detak ($f_{clk} = 1/T_{clk}$) mempercepat laju instruksi, tetapi dibatasi oleh jalur kritis (*critical path delay*):
$$T_{clk} \ge t_{pcq} + t_{pd,comb} + t_{setup}$$
Di mana:
*   $t_{pcq}$: Propagation delay register (clock-to-Q).
*   $t_{pd,comb}$: Latensi propagasi logika kombinasional terpanjang.
*   $t_{setup}$: Setup time flip-flop penerima.
Jika logika kombinasional terlalu kompleks, frekuensi clock harus diturunkan, atau desainer harus memecah sirkuit melalui teknik pipelining dengan biaya penambahan register dan latensi siklus awal.

---

## SEKSI 11 — BEST PRACTICES

### 1. Praktik Perancangan Logika Digital
*   **Desain Sinkron Penuh (*Fully Synchronous Design*):** Hindari penggunaan sinyal logika kombinasional sebagai input clock flip-flop (*gated clocks* tanpa sel khusus). Selalu gunakan satu master clock yang terdistribusi seragam via *clock tree synthesis* untuk menghindari *skew*.
*   **Penyederhanaan K-Map Sistematis:** Turunkan ekspresi logika ke bentuk minimal guna mengurangi kedalaman tingkat gerbang (*gate levels*), yang berdampak linier terhadap penurunan propagasi waktu tunda.
*   **Isolasi Domain Clock (CDC):** Bila data melintasi domain frekuensi berbeda, wajib gunakan *dual flip-flop synchronizer* atau asinkron FIFO untuk mencegah propagasi status metastabil.

### 2. Praktik Rekayasa Perangkat Lunak Terhadap Arsitektur Komputer
*   **Data Alignment:** Selalu deklarasikan struktur memori dengan *alignment* kelipatan ukuran native word CPU (misalnya 4-byte atau 8-byte). Data yang tidak sejajar (*unaligned*) memaksa memori controller melakukan dua siklus pembacaan bus dan *bit-shifting* tambahan.
*   **Branch Predictor Friendliness:** Tulis kode dengan branch yang terprediksi secara konsisten. Hindari percabangan tak menentu di dalam *hot loop*, manfaatkan ekspresi aritmatika kondisional (`cmov` pada x86) daripada lompatan instruksi (`jmp/jne`).
*   **Memori Terpadu dan Cache-Line:** Pahami bahwa paradigma Von Neumann berlanjut ke hierarki cache. Baca data secara sekuensial (spatial locality) untuk meminimalkan *cache miss* yang memicu akses berulang ke DRAM utama yang lambat.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **Mengabaikan Setup & Hold Time Violations:**
    *   *Gejala:* Data yang disimpan di register korup secara acak saat suhu chip naik atau tegangan suplai berfluktuasi tipis.
    *   *Akar Masalah:* Input $D$ berubah tepat pada jendela waktu sensitif di sekitar *rising clock edge*, menyebabkan flip-flop memasuki kondisi **metastabilitas** (osilasi sebelum stabil pada status biner acak).
2.  **Terjadinya Logic Glitch / Hazards:**
    *   *Gejala:* Terjadi denyut sinyal (*spike*) tegangan sesaat yang tidak diinginkan pada output kombinasional.
    *   *Akar Masalah:* Jalur perambatan yang memiliki jumlah gerbang berbeda menyebabkan input ke gerbang terakhir tiba pada waktu yang berselisih beberapa pikodetik (*static hazard*). Solusi: Tambahkan *consensus term* pada peta K-Map.
3.  **Kesalahan Asumsi Ukuran Word & Endianness:**
    *   *Gejala:* Pembacaan data multitype dari buffer jaringan atau file biner menghasilkan nilai acak pada arsitektur CPU berbeda.
    *   *Akar Masalah:* Kebingungan tata letak urutan byte antara Little-Endian (byte paling tidak signifikan pada alamat terendah, e.g., x86/ARM default) dan Big-Endian (byte paling signifikan pada alamat terendah, e.g., Network Byte Order).
4.  **Looping Menggunakan Tipe Data Signed Mengakibatkan Overflow:**
    *   *Gejala:* Program memasuki *infinite loop* atau memicu *undefined behavior* saat optimasi compiler tingkat tinggi diaktifkan.
    *   *Akar Masalah:* Overflow pada integer bertanda (*signed two's complement*) diatur oleh standar C sebagai *undefined behavior*, berbeda dengan integer tak bertanda (*unsigned*) yang memiliki jaminan wrap-around secara modular ($2^N$).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Desain Logika Kombinasional (Multiplexer 4-to-1)
*   **Tingkat Kesulitan:** Dasar
*   **Tugas:** Turunkan ekspresi Boolean minimal dan rancang diagram logika untuk Multiplexer 4-ke-1 (input: $I_0, I_1, I_2, I_3$, selector: $S_1, S_0$, output: $Y$).
*   **Instruksi:** Buat fungsi C `uint8_t mux4to1(uint8_t i0, uint8_t i1, uint8_t i2, uint8_t i3, uint8_t s0, uint8_t s1)` murni menggunakan operator bitwise masking dan OR, tanpa menggunakan pernyataan percabangan kondisional (`if`, `switch`, operator ternary).

### Latihan 2: Implementasi Finite State Machine (Detektor Sekuens Biner)
*   **Tingkat Kesulitan:** Menengah
*   **Tugas:** Rancang FSM tipe Mealy yang mendeteksi urutan biner berulang `1011` dari aliran bit serial sinkron.
*   **Spesifikasi:**
    *   Gambarkan diagram transisi *state*.
    *   Hitung jumlah Flip-Flop minimum yang diperlukan.
    *   Tulis kode C untuk FSM state-machine runner yang menerima array bit biner input dan menghasilkan array output yang menunjukkan kapan pola `1011` ditemukan.

### Latihan 3: Ekstensi Instruksi Arsitektur Von Neumann (TinyVM-8)
*   **Tingkat Kesulitan:** Lanjutan
*   **Tugas:** Ambil kode sumber dari Seksi 09 dan tambahkan fitur perangkat keras virtual berikut:
    1.  Dua register baru: $R_1$ dan $R_2$ (mengubah mesin dari berbasis akumulator tunggal menjadi register-based ALU).
    2.  Instruksi baru:
        *   `OP_CMP R1, R2` (Menyetel Flag: Zero, Negative).
        *   `OP_JMP addr` (Unconditional Jump).
        *   `OP_JL addr` (Jump if Less than, dievaluasi saat Negative flag aktif).
    3.  Tulis program assembly-code dalam memory array yang menghitung nilai faktorial dari angka 4 ($4! = 24$).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Periksa pemahaman Anda dengan menjawab pertanyaan-pertanyaan berikut:

#### 1. Jika sebuah gerbang NAND memiliki 2 input, kombinasi input manakah yang menghasilkan nilai output 0?
*   A. Input A = 0, Input B = 0
*   B. Input A = 0, Input B = 1
*   C. Input A = 1, Input B = 0
*   D. Input A = 1, Input B = 1
*   *Jawaban yang Benar:* **D**
*   *Rasional:* Gerbang NAND menghasilkan komplemen dari gerbang AND. AND hanya bernilai 1 jika kedua input 1 ($1 \cdot 1 = 1$). Maka komplemennya ($\overline{1 \cdot 1}$) adalah 0.

#### 2. Apa perbedaan mendasar antara D-Latch dan D-Flip-Flop?
*   A. D-Latch bersifat sinkron, D-Flip-Flop asinkron.
*   B. D-Latch sensitif terhadap level sinyal (level-sensitive), D-Flip-Flop sensitif terhadap transisi sinyal (edge-triggered).
*   C. D-Latch tidak memiliki status metastabil, D-Flip-Flop memiliki status metastabil.
*   D. D-Latch hanya menyimpan sinyal inversi, D-Flip-Flop menyimpan nilai identitas.
*   *Jawaban yang Benar:* **B**
*   *Rasional:* Latch mempertahankan transparansi selama level sinyal Enable aktif, sedangkan Flip-Flop hanya mengubah status output pada saat sinyal clock bertransisi (positif atau negatif edge).

#### 3. Masalah utama yang dirumuskan sebagai "Von Neumann Bottleneck" mengacu pada:
*   A. Kecepatan clock CPU yang tidak bisa melampaui limit termal semikonduktor.
*   B. Kerentanan korupsi data ketika CPU dan periferal membaca I/O bersamaan.
*   C. Keterbatasan throughput data akibat saluran bus tunggal yang dibagi bersama antara pengambilan instruksi dan pemindahan data operand.
*   D. Hambatan komputasi akibat instruksi non-linear seperti conditional branching.
*   *Jawaban yang Benar:* **C**
*   *Rasional:* Karena program dan data berbagi bus memori yang sama, CPU tidak dapat membaca instruksi baru sekaligus membaca/menulis memori data dalam siklus jam yang sama.

#### 4. Kriteria waktu minimum di mana sinyal data input harus dipertahankan stabil SEBELUM tepi aktif jam (clock edge) tiba disebut:
*   A. Hold Time
*   B. Propagation Delay
*   C. Setup Time
*   D. Clock Skew
*   *Jawaban yang Benar:* **C**
*   *Rasional:* *Setup time* ($t_{su}$) adalah durasi minimum input data harus valid dan stabil sebelum clock edge tiba agar dapat disampel secara deterministik.

#### 5. Berapa banyak gerbang NAND 2-input minimal yang dibutuhkan untuk merepresentasikan satu gerbang XOR 2-input ($A \oplus B$)?
*   A. 3
*   B. 4
*   C. 5
*   D. 6
*   *Jawaban yang Benar:* **B**
*   *Rasional:* Konstruksi standar $A \oplus B$ memerlukan 4 gerbang NAND:
    $N_1 = \overline{A \cdot B}$,
    $N_2 = \overline{A \cdot N_1}$,
    $N_3 = \overline{B \cdot N_1}$,
    $Out = \overline{N_2 \cdot N_3} = A \oplus B$.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1.  **Patterson, D. A., & Hennessy, J. L.** *Computer Organization and Design: The Hardware/Software Interface (RISC-V Edition)*. Morgan Kaufmann.
2.  **Harris, D., & Harris, S.** *Digital Design and Computer Architecture*. Morgan Kaufmann.
3.  **Tanenbaum, A. S., & Austin, T.** *Structured Computer Organization (6th Edition)*. Pearson.
4.  **Mano, M. M., & Ciletti, M. D.** *Digital Design: With an Introduction to the Verilog HDL*. Pearson.
5.  **Nisan, N., & Schocken, S.** *The Elements of Computing Systems: Building a Modern Computer from First Principles (Nand2Tetris)*. MIT Press.
6.  *IEEE Standard for VHDL Language (IEEE Std 1076)* & *Verilog Hardware Description Language (IEEE Std 1364)*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

Modul ini telah menguraikan jembatan evolusioner dari sirkuit sakelar fisik hingga terciptanya mesin komputasi otonom terpadu:
1.  **Sistem Digital** dibangun di atas Aljabar Boolean menggunakan transistor CMOS yang dirangkai menjadi gerbang universal (NAND/NOR).
2.  **Logika Kombinasional** memproses nilai data tanpa kapasitas penyimpanan internal, di mana fungsi aritmatika kompleks seperti ALU diturunkan dari unit mendasar seperti Half Adder, Full Adder, dan Multiplexer.
3.  **Logika Sekuensial** mengintroduksi dimensi waktu dan memori internal melalui mekanisme umpan balik (*feedback*). Transisi dari Latch ke Edge-Triggered Flip-Flop memungkinkan sinkronisasi deterministik di bawah koordinasi sinyal detak (*clock*).
4.  **Arsitektur Von Neumann** memadukan sirkuit kombinasional (ALU) dan elemen sekuensial (Register, PC, Memory) ke dalam paradigma *stored-program*. Siklus berulang *Fetch, Decode, Execute, Writeback* menjadi basis fisik eksekusi kode mesin pada hampir seluruh arsitektur komputer modern.

---

## SEKSI 17 — GLOSARIUM

*   **ALU (Arithmetic Logic Unit):** Sirkuit kombinasional yang bertugas mengeksekusi komputasi aritmatika biner (penjumlahan, pengurangan) dan logika bitwise (AND, OR, NOT, XOR).
*   **Propagation Delay ($t_{pd}$):** Durasi waktu yang dibutuhkan oleh perubahan sinyal pada input gerbang logika untuk menghasilkan perubahan yang stabil pada outputnya.
*   **Metastabilitas:** Keadaan tidak stabil di mana sirkuit digital bistabil (seperti flip-flop) berosilasi di antara logika 0 dan 1 akibat pelanggaran *setup/hold time*.
*   **Program Counter (PC):** Register arsitektur khusus yang memegang alamat memori dari instruksi selanjutnya yang akan dieksekusi oleh prosesor.
*   **Datapath:** Kumpulan register, ALU, multiplexer, dan bus internal yang melakukan operasi pemrosesan data aktual dalam CPU.
*   **Control Unit (CU):** Modul pengendali mikroarsitektur yang menerjemahkan opcode instruksi menjadi sinyal kendali perangkat keras (*control lines*).
*   **Flip-Flop:** Elemen sirkuit bistabil sinkron yang menyimpan 1-bit data biner dan hanya memperbarui statusnya pada tepi sinyal detak (*clock edge*).
*   **Von Neumann Bottleneck:** Penurunan efisiensi kinerja throughput sistem akibat penggunaan jalur bus terpadu tunggal untuk akses program instruksi dan transfer data memori.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Pedoman Pedagogis:** Mulailah pengajaran dengan demonstrasi perangkat keras menggunakan simulator visual (seperti *Logisim-Evolution*) sebelum beralih ke representasi kode perangkat lunak (C/C++). Sangat disarankan menugaskan mahasiswa merancang Adder dan D-Flip-Flop langsung dari gerbang logika primitif NAND.
*   **Titik Rawan Miskonsepsi:** Mahasiswa sering kali mengira clock "mendorong" data secara kontinu. Tekankan bahwa logika kombinasional bekerja secara asinkron mengikuti hukum propagasi fisika semikonduktor, dan Flip-Flop bertindak sebagai "dinding penahan bendungan" yang hanya membuka gerbang sekilas pada saat *clock edge*.
*   **Eksperimen Laboratorium:** Gunakan implementasi virtual CPU pada Seksi 09 sebagai basis tugas laboratorium. Minta siswa menambahkan stack pointer ($SP$) dan mekanisme pemanggilan fungsi primitif (`CALL` / `RET`).

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Oktober 2023):**
    *   Rilis awal materi kurikulum Arsitektur Komputer & Sistem Digital.
    *   Integrasi materi aljabar Boolean, sirkuit sekuensial, dan model Von Neumann.
    *   Penyediaan kode emulator C99 (TinyVM-8) untuk memvalidasi siklus *Fetch-Decode-Execute*.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `CS-CORE-01-03` — Representasi Data Tingkat Rendah, Fixed-Point, dan Floating-Point IEEE-754.
*   **Modul Saat Ini:** `CS-CORE-02-01` — Fondasi Sistem Digital: Dari Gerbang Logika, Logika Sekuensial, hingga Eksekusi Von Neumann.
*   **Modul Berikutnya:** `CS-CORE-02-02` — Instruksi Set Architecture (ISA): Assembly RISC-V, Mode Pengalamatan, dan Pipeline Dasar.