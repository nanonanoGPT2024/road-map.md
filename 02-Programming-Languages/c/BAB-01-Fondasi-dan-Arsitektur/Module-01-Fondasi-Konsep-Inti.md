# Bab 01: Fondasi Bahasa C & Arsitektur Komputasi Sistem Rendah
## Module 01: Arsitektur Eksekusi C, Toolchain Kompilasi, dan Anatomi Program

---

### 1. Learning Objectives (Tujuan Pembelajaran)
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
*   Menganalisis 4 fase pipeline toolchain kompilasi C (*Preprocessing*, *Compilation*, *Assembly*, *Linking*) hingga terbentuk binary executable ELF/Mach-O/PE.
*   Mengidentifikasi struktur dan anatomi fungsi `main` sesuai standar ISO C (C11/C17/C23) beserta manajemen status terminasi program pada sistem operasi host.
*   Membedah pemetaan memori tingkat tinggi (*text*, *rodata*, *data*, *bss*, *stack*, *heap*) dari suatu program biner menggunakan utilitas GNU Binutils/LLVM.
*   Menghindari jebakan *undefined behavior* mendasar seperti *format string attack* pada I/O awal dan terminasi status di luar batas POSIX (0-255).
*   Menulis, mengompilasi, dan merekayasa program CLI standar industri berbasis C17 menggunakan compiler flags modern (`-Wall`, `-Wextra`, `-Werror`, `-pedantic`).

---

### 2. Concept (Konsep Dasar)
Bahasa C dirancang sebagai bahasa pemrograman imperatif terstruktur yang memetakan instruksi kode langsung ke primitif arsitektur mesin (*von Neumann architecture*) dengan overhead runtime seminimal mungkin (*near-zero abstraction cost*). Berbeda dengan bahasa yang berjalan di atas Virtual Machine (JVM, CLR) atau Interpreter (Python, Ruby), C beroperasi langsung pada model memori linear sistem operasi induk (*host OS*). Program C tidak memiliki *Garbage Collector*, *runtime exception handler*, atau *type reflection* bawaan; setiap byte memori dan siklus instruksi dikendalikan secara eksplisit oleh instruksi biner yang dihasilkan compiler.

---

### 3. Why It Matters (Mengapa Penting)
Keberadaan C sebagai fondasi komputasi modern tidak tergantikan pada domain berikut:
*   **Kernel Sistem Operasi**: Linux, macOS (XNU), dan Windows NT mengandalkan C untuk manajemen page tables, interrupts, dan thread scheduling.
*   **Embedded Systems & IoT**: Mikrokontroler berdaya rendah (ARM Cortex-M, RISC-V, AVR) memiliki keterbatasan RAM (dalam orde kilobyte), di mana overhead runtime bahasa level tinggi mustahil dieksekusi.
*   **Runtime Engine & Runtimes VM**: Node.js (V8 engine), CPython, dan JVM ditulis menggunakan C/C++ untuk memaksimalkan throughput eksekusi.
*   **Deterministik Temporal**: C menjamin latensi eksekusi yang deterministik tanpa interupsi *Stop-the-World* dari garbage collector.

---

### 4. What It Is (Definisi & Karakteristik)
C adalah bahasa pemrograman tingkat menengah (*middle-level language*) yang statically typed, compiled, dan berbasis leksikal skop.
Karakteristik teknis utama:
1.  **Direct Memory Access**: Akses alamat memori fisik/virtual secara presisi via pointer arithmetic.
2.  **Deterministic Resource Management**: Alokasi dan dealokasi memori sepenuhnya ditentukan oleh program (`malloc`/`free` atau *stack allocation*).
3.  **Strict Source to Binary Compilation**: Kode sumber bertransformasi menjadi *native machine code* spesifik terhadap ISA (*Instruction Set Architecture*) target (x86_64, AArch64, RISC-V).
4.  **Minimal Runtime Environment**: Program C hanya membutuhkan *C runtime library* minimal (`crt0.o` dan `libc`) untuk menginisialisasi stack, heap, dan argumen sebelum memanggil fungsi `main`.

---

### 5. How It Works (Mekanisme Kerja / Arsitektur)
Transformasi dari kode sumber `.c` menjadi executable biner melewati 4 tahap terisolasi:

```
[Source: main.c]
       │
       ▼ (1) Preprocessing: gcc -E (Ekspansi Macro, Evaluasi #include, Strip Comments)
[Translation Unit: main.i]
       │
       ▼ (2) Compilation: gcc -S (Lexing, Parsing, AST, SSA, Optimasi, Emisi Assembly)
[Assembly Source: main.s]
       │
       ▼ (3) Assembly: gcc -c (Assembler/as -> Translasi Opcode Biner, Tabel Simbol)
[Relocatable Object: main.o]
       │
       ▼ (4) Linking: ld (Resolusi Simbol, Relokasi Alamat, Merging Segmen libc)
[Executable Binary: a.out / ELF]
```

1.  **Preprocessing (`cpp`)**: Menghapus komentar, mengikutsertakan header files (`#include`), dan mengekspansi macro direktif (`#define`, `#ifdef`). Outputnya adalah *Pure Translation Unit*.
2.  **Compilation (`cc1`)**: Mentranslasikan Translation Unit menjadi *Abstract Syntax Tree* (AST), intermediate representation (IR), melakukan optimasi (misalnya *loop unrolling*, *constant folding*), lalu mengemisi instruksi perakitan target (*assembly code*).
3.  **Assembly (`as`)**: Mengonversi instruksi assembly ke instruksi mesin biner (*machine code*), menghasilkan *Relocatable Object File* berformat ELF/Mach-O/COFF. Simbol eksternal masih berupa referensi kosong (*unresolved references*).
4.  **Linking (`ld`)**: Menautkan semua file `.o` dan static/dynamic library (`libc.so`, `crt1.o`), menyelesaikan resolusi simbol (*symbol resolution*), dan menentukan alamat memori absolut/relatif segmen (*relocation*).

---

### 6. Diagram ASCII: Struktur Eksekusi & Memori ELF

```
+-------------------------------------------------------+
|             Linux Virtual Memory Space                |
|             (Ukuran: misal 48-bit Canonical)          |
+-------------------------------------------------------+ 0xFFFFFFFFFFFFFFFF
| Kernel Space (Direct Physical Map, Drivers, Kernel)   |
+-------------------------------------------------------+ 0xFFFF800000000000
| User Space Memory Map:                                |
|                                                       |
|   +-----------------------------------------------+   |
|   | Stack (Tumbuh ke Bawah / Downward)            |   |
|   | Frame: main(argc, argv), Local Variables      |   |
|   +-----------------------------------------------+   |
|                           |                           |
|                           v                           |
|                                                       |
|                           ^                           |
|                           |                           |
|   +-----------------------------------------------+   |
|   | Heap (Tumbuh ke Atas via brk/sbrk/mmap)       |   |
|   +-----------------------------------------------+   |
|   | BSS Segment (Uninitialized Global/Static = 0) |   |
|   +-----------------------------------------------+   |
|   | Data Segment (Initialized Global/Static != 0) |   |
|   +-----------------------------------------------+   |
|   | RODATA Segment (Read-Only: String Literals)   |   |
|   +-----------------------------------------------+   |
|   | Text Segment (Machine Code Instructions)      |   |
|   +-----------------------------------------------+   | 0x0000000000400000
+-------------------------------------------------------+ 0x0000000000000000
```

---

### 7. Memory Model & Internals
Ketika OS mengeksekusi binary C (misal via syscall `execve`), kernel membaca *ELF Program Headers* dan memetakan segmen berikut ke dalam *Virtual Address Space*:
*   **`.text`**: Menyimpan instruksi assembly biner CPU. Bersifat *Read-Only* dan *Executable* (`r-x`). Pelanggaran penulisan memicu `SIGSEGV`.
*   **`.rodata`**: Read-only data. Menyimpan literal string seperti `"Hello, World!\n"` dan konstanta `const`. Bersifat `r--`.
*   **`.data`**: Menyimpan variabel global dan statis yang **sudah diinisialisasi** dengan nilai non-zero. Bersifat `rw-`.
*   **`.bss`** (*Block Started by Symbol*): Menyimpan variabel global dan statis yang **belum diinisialisasi** atau diinisialisasi dengan nol. Segmen ini tidak memakan ruang di file biner (hanya mencatat kebutuhan alokasi byte). Kernel mengisi segmen ini dengan byte `0` saat inisialisasi runtime (`rw-`).
*   **`Stack`**: Struktur LIFO otomatis untuk variabel lokal, parameter fungsi, dan *return address*. Dikelola oleh register `$rsp` / `$rbp` pada x86_64.
*   **`Heap`**: Ruang alokasi dinamik manual yang dikelola runtime allocator via `malloc()`, `calloc()`, atau `realloc()`.

---

### 8. Syntax & Primitives
Struktur signature standard ISO C untuk titik masuk (*entry point*) program:

```c
// Bentuk 1: Tanpa argumen CLI
int main(void);

// Bentuk 2: Dengan penanganan argumen CLI (Standar Hosted Environment)
int main(int argc, char *argv[]);
// atau ekuivalen secara leksikal:
int main(int argc, char **argv);
```

*   `argc` (*Argument Count*): Integer yang menyimpan jumlah total string yang dikirimkan via antarmuka baris perintah (termasuk nama executable). Nilai selalu $\ge 1$.
*   `argv` (*Argument Vector*): Array of pointers ke string karakter null-terminated (`char*`). `argv[0]` adalah path executable, `argv[argc]` dijamin bernilai `NULL` oleh standar ISO C.
*   `return 0` / `EXIT_SUCCESS`: Mengembalikan status code ke shell OS induk. Nilai di luar range `0-255` akan mengalami pemotongan (*bitwise truncation*) modulo 256 pada POSIX.

---

### 9. Step-by-Step Implementation (Dekomposisi Toolchain Manual)

#### Langkah 1: Buat file kode sumber mentah
```bash
cat << 'EOF' > pipeline_demo.c
#define MAGIC_STATUS 0

int main(void) {
    return MAGIC_STATUS;
}
EOF
```

#### Langkah 2: Jalankan Fase Preprocessing
```bash
gcc -E pipeline_demo.c -o pipeline_demo.i
```
*Inspeksi:* Buka `pipeline_demo.i`. Seluruh directive `#define` telah digantikan secara literal, dan comments (jika ada) dieliminasi.

#### Langkah 3: Jalankan Fase Kompilasi ke Assembly
```bash
gcc -S -O0 pipeline_demo.i -o pipeline_demo.s
```
*Inspeksi:* Buka `pipeline_demo.s`. Anda melihat instruksi CPU murni:
```assembly
.globl  main
.type   main, @function
main:
    pushq   %rbp
    movq    %rsp, %rbp
    movl    $0, %eax
    popq    %rbp
    ret
```

#### Langkah 4: Jalankan Fase Perakitan (Assemble) ke Object Code
```bash
gcc -c pipeline_demo.s -o pipeline_demo.o
```
*Inspeksi:* Periksa tipe file menggunakan `file pipeline_demo.o`. Output: `ELF 64-bit LSB relocatable`.

#### Langkah 5: Jalankan Fase Linking
```bash
gcc pipeline_demo.o -o pipeline_demo
```
Linker menautkan CRT (*C Runtime*) entry code (`_start`), yang kemudian memanggil fungsi `main`.

---

### 10. Minimal Reproducible Example
Program ISO C17 valid terkonfirmasi:

```c
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    /* Menulis string konstan ke stdout stream */
    if (puts("Low-level C Initialization Successful.") == EOF) {
        return EXIT_FAILURE; // Nilai non-zero mengindikasikan kegagalan
    }
    
    return EXIT_SUCCESS; // Nilai 0 mengindikasikan terminasi sukses
}
```

---

### 11. Production-Grade / Practical Example
Berikut adalah implementasi CLI parameter parser sederhana berstandar industri dengan penanganan error I/O dan validasi defensive tanpa memory leak.

```c
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <limits.h>

/**
 * Mengonversi string ke integer 32-bit bertanda dengan proteksi overflow.
 * Mengembalikan 0 jika sukses, -1 jika parsing invalid/overflow.
 */
static int parse_safe_int(const char *str, int *out_val) {
    char *endptr = NULL;
    errno = 0; // Reset global error indicator

    long val = strtol(str, &endptr, 10);

    // Kasus 1: Terjadi overflow/underflow pada rentang tipe 'long'
    if ((errno == ERANGE && (val == LONG_MAX || val == LONG_MIN)) || (errno != 0 && val == 0)) {
        return -1;
    }

    // Kasus 2: Tidak ada karakter numerik yang dapat dikonversi
    if (endptr == str) {
        return -1;
    }

    // Kasus 3: Ada karakter non-numerik yang tersisa di akhir string
    if (*endptr != '\0') {
        return -1;
    }

    // Kasus 4: Nilai melebihi kapasitas representasi arsitektur tipe 'int'
    if (val > INT_MAX || val < INT_MIN) {
        return -1;
    }

    *out_val = (int)val;
    return 0;
}

int main(int argc, char *argv[]) {
    // Validasi parameter baris perintah
    if (argc != 2) {
        // Logging kesalahan selalu diarahkan ke standard error (stderr)
        fprintf(stderr, "Error: Argumentasi tidak valid.\n");
        fprintf(stderr, "Penggunaan: %s <nilai_integer>\n", argv[0]);
        return EXIT_FAILURE;
    }

    int parsed_value = 0;
    if (parse_safe_int(argv[1], &parsed_value) != 0) {
        fprintf(stderr, "Fatal: Input '%s' bukan representasi integer 32-bit yang valid.\n", argv[1]);
        return EXIT_FAILURE;
    }

    // Emisi hasil ke standard output (stdout)
    if (printf("Parsing Berhasil. Nilai: %d (Hex: 0x%08X)\n", parsed_value, (unsigned int)parsed_value) < 0) {
        perror("Gagal menulis ke stdout");
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
```

---

### 12. Edge Cases, Failure Modes & Pitfalls
*   **Format String Attack**: Menulis `printf(argv[1])` alih-alih `printf("%s", argv[1])`. Jika user memasukkan `%x %x %n`, penyerang dapat membaca nilai memory stack atau menimpa memory sembarang.
*   **POSIX Exit Code Truncation**: Status terminasi dari `exit(status)` atau `return status` hanya mengekspos **8-bit rendah** (`status & 0xFF`) ke parent process.
    ```c
    return 256; // Shell parent (bash: echo $?) akan membaca status: 0 (Sukses palsu!)
    ```
*   **Undefined Behavior pada `argv` Out-of-Bounds**: Mengakses `argv[argc]` adalah legal (bernilai `NULL`), tetapi dereferensi `*argv[argc]` menghasilkan *Segmentation Fault* (`SIGSEGV`).
*   **Implicit Function Declaration**: Pada standard C lama (C89), memanggil fungsi tanpa menyertakan file header menghasilkan *implicit int return*. Pada C99/C11/C17/C23, ini adalah *constraint violation*.

---

### 13. Compilation, Linking & Build Process

#### Hardened Compilation Command
Gunakan opsi compiler ketat untuk mendeteksi deviasi standar pada saat build time:
```bash
gcc -std=c17 -Wall -Wextra -Wpedantic -Werror -Wformat=2 -Wshadow -O2 main.c -o app_runner
```
*   `-std=c17`: Memaksa standar ISO C edisi 2017.
*   `-Wall -Wextra -Wpedantic`: Mengaktifkan seluruh diagnostik peringatan kepatuhan sintaksis.
*   `-Werror`: Mengubah setiap peringatan (*warning*) menjadi kegagalan kompilasi (*error*).
*   `-Wformat=2`: Mendeteksi potensi serangan security pada `printf`/`scanf`.
*   `-O2`: Optimasi level 2 untuk efisiensi instruksi CPU tanpa degradasi integritas debug.

#### Minimal Production Makefile
```makefile
CC ?= gcc
CFLAGS ?= -std=c17 -Wall -Wextra -Wpedantic -Werror -O2
TARGET = app_runner
SRCS = main.c
OBJS = $(SRCS:.c=.o)

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(OBJS) -o $(TARGET)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)
```

---

### 14. Debugging & Memory Profiling

#### 1. Inspeksi Segmen Memori Biner via Binutils
Gunakan `size` untuk memverifikasi footprint memori:
```bash
$ size app_runner
   text    data     bss     dec     hex filename
   2048     616       8    2672     a70 app_runner
```

#### 2. Inspeksi Symbol Table & Disassembly via `objdump`
```bash
# Memeriksa simbol main
$ objdump -t app_runner | grep main
00000000000011a9 g     F .text  000000000000008c              main

# Membedah instruksi assembly dari biner final
$ objdump -d --no-show-raw-insn -M intel app_runner
```

#### 3. Low-Level Execution Tracing via GDB
```bash
$ gdb ./app_runner
(gdb) break main
Breakpoint 1 at 0x11b5
(gdb) run 12345
(gdb) info registers rsp rbp rip
(gdb) x/10i $rip          # Periksa 10 instruksi mesin berikutnya
(gdb) print argv[0]       # Cetak pointer argumen pertama
(gdb) continue
```

---

### 15. Trade-offs & Alternatives

| Dimensi | C (ISO C17) | Modern C++ (C++20) | Rust (2021 Edition) |
| :--- | :--- | :--- | :--- |
| **Abstraksi** | Rendah / Direct Hardware | Tinggi via Zero-Cost Template/OOP | Tinggi via Trait-based System |
| **Memory Safety** | Manual (Raw Pointer, Rawan UB) | Manual / Smart Pointers | Terjamin saat Compile (*Borrow Checker*) |
| **Toolchain & ABI** | Stabil secara de-facto lintas dekade | Kompleks, rapuh antar versi compiler | Tidak ada stable ABI internal |
| **Ukuran Runtime** | Minimal (`crt0`, `libc`) | Membutuhkan exception unwinding overhead | Minimal (dapat berjalan `no_std`) |
| **Waktu Kompilasi** | Sangat Cepat | Lambat (Instansiasi Template masif) | Lambat (Analisis Borrow Checking ketat) |

---

### 16. Performance Implications
*   **Startup Overhead**: Inisialisasi program C membutuhkan waktu eksekusi dalam orde mikrodetik ($\mu s$), berkebalikan dengan JVM atau CLR yang membutuhkan ratusan milidetik untuk bootstrap class loader dan JIT compiler.
*   **Instruction Cache Miss**: Binary C yang kecil menghasilkan *footprint* L1 Instruction Cache (`L1i`) yang efisien.
*   **I/O Stream Buffering**: Fungsi `printf`/`puts` menggunakan buffer internal libc (`BUFSIZ`, biasanya 4096 atau 8192 bytes). Mengarahkan stream ke terminal beroperasi dalam *line-buffered mode*, sedangkan redirecting ke file beroperasi dalam *fully-buffered mode*.

---

### 17. Best Practices & Coding Standards
*   **MISRA C / CERT-C Rules**:
    *   *Rule 1*: Selalu verifikasi return value dari setiap fungsi library standard I/O (`printf`, `scanf`, `puts`).
    *   *Rule 2*: Jangan mengandalkan *implicit int* pada tipe pengembalian fungsi; deklarasikan `int main(void)` secara eksplisit.
    *   *Rule 3*: Hindari pemanggilan library berstatus deprecated seperti `gets()` (resmi dihapus sejak C11) dan ganti dengan `fgets()` yang menerapkan batas buffer eksplisit.
*   **Inisialisasi Variabel**: Selalu inisialisasi variabel lokal pada saat deklarasi guna mencegah pembacaan data sampah (*indeterminate/garbage value*) dari register stack frame lama.

---

### 18. Security Considerations
*   **Buffer Insecurity**: Standard library C tidak melakukan verifikasi *bounds checking* secara otomatis.
*   **Input Validation Attack Surface**: Argumen yang dimasukkan via `argv` berasal dari untrusted context (shell user). Seluruh string `argv` harus divalidasi panjang karakternya, tipenya, dan encodingnya sebelum diproses ke logika internal.
*   **Binary Hardening Flags**:
    Saat mengompilasi biner ke lingkungan produksi, selalu aktifkan mitigasi kernel:
    *   `-fstack-protector-strong`: Mencegah modifikasi *stack frame return address* via stack canary.
    *   `-D_FORTIFY_SOURCE=2`: Memeriksa overflow pada fungsi manipulasi memory/string secara runtime.
    *   `-Wl,-z,relro,-z,now`: Mengunci *Global Offset Table* (GOT) menjadi Read-Only untuk mencegah teknik eksploitasi GOT Overwrite.

---

### 19. Self-Assessment / Hands-on Lab

#### Tugas Mandiri
1.  **Analisis Toolchain**: Modifikasi file `main.c` dengan menambahkan directive `#define SYS_ARCH 64`. Gunakan flag `-E` dan temukan baris mana nilai tersebut diinjeksikan dalam Translation Unit.
2.  **Segmen Forensik**:
    *   Deklarasikan `int global_var = 100;` (Analisis: Masuk ke segmen apa?)
    *   Deklarasikan `int uninit_var;` (Analisis: Masuk ke segmen apa?)
    *   Deklarasikan `const char *str = "Test";` (Analisis: Masuk ke segmen apa?)
    *   Verifikasi temuan Anda secara presisi menggunakan perintah terminal:
        ```bash
        objdump -h <nama_binary>
        ```
3.  **Audit Kerentanan**:
    Diberikan program berikut:
    ```c
    #include <stdio.h>
    int main(int argc, char *argv[]) {
        printf(argv[1]);
        return 0;
    }
    ```
    *   Kompilasi program dengan `gcc -Wall`. Catat pesan warning yang muncul.
    *   Jalankan program dengan argumen: `./a.out "%x.%x.%x.%x"`.
    *   Dokumentasikan apa yang ditampilkan di terminal dan jelaskan mekanismenya berdasarkan layout stack memory!

---

### 20. Summary & Next Steps
*   Program C tidak berjalan dalam isolasi virtual; program C berinteraksi langsung dengan stack frame CPU, virtual address space OS, dan tabel segmentasi format file executable (ELF).
*   Proses kompilasi terbagi menjadi 4 sekat terisolasi: Preprocessor, Compiler, Assembler, dan Linker.
*   Fungsi `main` adalah antarmuka formal antara program ruang pengguna (*user space*) dan status eksekusi kernel/shell.

**Langkah Selanjutnya (Module 02):**
Membedah sistem tipe data fundamental C, representasi bilangan komplemen dua (*two's complement*), penanganan *endianness*, serta perilaku *type promotion* dan *integer overflow/underflow* pada arsitektur modern.