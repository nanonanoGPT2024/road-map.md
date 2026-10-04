# BAB 01: Quiz, Challenge, & Knowledge Check
**Arsitektur Kompilasi, Linking, & Memory Layout**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Dekonstruksi Rantai Toolchain Kompilasi
Uraikan secara presisi transformasi representasi data dan instruksi yang terjadi pada empat tahapan utama toolchain C (*Preprocessing*, *Compilation*, *Assembly*, dan *Linking*). Sebutkan nama engine internal standar (misalnya pada GCC: `cpp`, `cc1`, `as`, `ld`), format input/output artefak pada masing-masing fase, serta jelaskan mengapa tahap sintaksis dan optimasi semantik diisolasi sepenuhnya sebelum emisi kode mesin spesifik arsitektur target.

### Soal 1.2: Dualitas ELF: Sections vs. Segments
Dalam format biner *Executable and Linkable Format* (ELF), jelaskan perbedaan fundamental antara konsep **Section** (didefinisikan dalam *Section Header Table*) dan **Segment** (didefinisikan dalam *Program Header Table*). Mengapa linker membutuhkan Section View, sedangkan OS Kernel Loader (`execve`) secara eksklusif hanya memproses Segment View?

### Soal 1.3: Mekanisme Alokasi BSS (*Block Started by Symbol*)
Segment/Section `.bss` menampung variabel global dan statis yang tidak diinisialisasi atau diinisialisasi dengan nilai nol. Jelaskan mengapa ukuran biner ELF pada disk tidak bertambah secara proporsional ketika Anda mendeklarasikan array global `static uint8_t buffer[1024 * 1024 * 50] = {0};`. Terangkan bagaimana kernel OS dan *page fault handler* mengalokasikan memori fisik nyata untuk segmen ini saat eksekusi runtime biner dimulai.

### Soal 1.4: Dynamic Linking vs. Static Linking Memory Footprint
Bandingkan trade-off konsumsi memori virtual (*Virtual Memory Area* / VMA) dan memori fisik (*Resident Set Size* / RSS) antara biner yang di-*link* secara statis (`-static`) versus dinamis. Analisis bagaimana kernel Linux memanfaatkan fitur *Copy-on-Write* (CoW) dan *shared page mappings* pada segmen instruksi (`.text`) dari Dynamic Shared Objects (DSO/`.so`) ketika 1.000 proses dari aplikasi yang sama dieksekusi secara konkuren.

### Soal 1.5: Segmentasi Anatomi Virtual Address Space (x86_64)
Gambarkan hierarki layout memori virtual proses 64-bit standar pada Linux (dari alamat terendah `0x0000000000000000` hingga alamat kanonikal tertinggi `0x7FFFFFFFFFFF` untuk user space). Definisikan letak dan karakteristik hak akses (*Read*, *Write*, *Execute* / RWX) untuk:
1. `.text`
2. `.rodata`
3. `.data`
4. `.bss`
5. Heap
6. Memory Mapping Segment (`mmap`)
7. User Stack
8. Vvar/Vdso
9. Kernel Space.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi Simbol: Strong vs. Weak Symbols & ODR Hazard
Dalam standar C dan GNU Linker (`ld`), bedakan definisi antara *Strong Symbol* dan *Weak Symbol*. Prediksikan apa yang terjadi secara eksak pada tahap linking apabila:
- File `a.c` mendefinisikan `int global_flag = 10;` dan file `b.c` mendefinisikan `int global_flag = 20;`.
- File `a.c` mendefinisikan `int global_flag;` (tentative definition) dan file `b.c` mendefinisikan `int global_flag = 20;`.
- Dua modul shared library (`libA.so` dan `libB.so`) mendefinisikan fungsi global non-static dengan signature dan nama yang identik `void process_payload(void)`. Bagaimana dynamic linker (`ld-linux.so`) menangani tabrakan (*collision*) ini saat runtime?

### Soal 2.2: Mekanisme PIC, GOT, dan PLT
Untuk menghasilkan *Position Independent Code* (PIC/PIE), kompilator tidak dapat meng-hardcode alamat absolut fungsi eksternal ke dalam segmen `.text`. Jelaskan siklus hidup pemanggilan fungsi shared library pertama kali via **Procedure Linkage Table (PLT)** dan **Global Offset Table (GOT)** menggunakan teknik *Lazy Binding*! Mengapa konfigurasi sekuritas modern menerapkan `-Wl,-z,relro,-z,now` (*Full RELRO*), dan apa konsekuensi strukturalnya terhadap GOT?

### Soal 2.3: Invarian ABI: Stack Frame & Alignment (System V AMD64)
Berdasarkan *System V AMD64 ABI*, jelaskan konvensi passing argumen fungsi melalui register CPU versus stack. Mengapa stack pointer (`%rsp`) **wajib** disejajarkan ke batas (*alignment*) 16-byte tepat sebelum instruksi `call` dieksekusi? Apa dampak struktural dan instruksional yang terjadi (misalnya emisi instruksi SSE/AVX seperti `movdqa`) jika invarian *stack alignment* ini dilanggar saat memanggil fungsi C dari inline assembly atau runtime kustom?

### Soal 2.4: Analisis Scoping Simbolik pada Object File
Diberikan kode C berikut:
```c
static int engine_id = 101;
int global_counter = 0;
const char build_tag[] = "v1.0.0";

void process(void) {
    static int local_state = 5;
    int ephemeral_val = 42;
}
```
Jelaskan pemetaan masing-masing variabel (`engine_id`, `global_counter`, `build_tag`, `local_state`, dan `ephemeral_val`) ke dalam:
1. Section ELF yang relevan (`.text`, `.rodata`, `.data`, `.bss`, atau Stack Frame).
2. Tipe visibilitas pada Symbol Table (`.symtab`) (Local, Global, atau None).
3. Apakah variabel tersebut menghasilkan entri pada *Relocation Table* (`.rela.data` / `.rela.text`) sebelum tahap linking final?

### Soal 2.5: Semantik `inline`, `static inline`, dan `extern inline` di C99/C11
Jelaskan perbedaan mendasar antara `static inline`, `inline` (tanpa static), dan `extern inline` dalam kaitannya dengan emisi simbol pada file objek (`.o`). Mengapa penempatan fungsi `inline` (tanpa static) di dalam file header (`.h`) dapat memicu kegagalan kompilasi *multiple definition error* atau *undefined reference error* tergantung pada level optimasi compiler (`-O0` vs `-O2`)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Produksi - Silent Variable Hijack pada High-Frequency Trading Core
Sebuah sistem *Order Execution Engine* berkinerja tinggi mengalami insiden kritis di lingkungan produksi: variabel konfigurasi risiko `uint64_t max_notional_limit` mendadak berubah nilainya secara anomali menjadi nilai pointer yang sangat besar segera setelah modul diagnostik dinamis (`libtelemetry.so`) dimuat menggunakan `dlopen()`. 

Kode pada core engine:
```c
// Engine Core (Static Binary)
uint64_t max_notional_limit = 5000000;
```
Kode pada modul `libtelemetry.so`:
```c
// Modul Telemetri yang dikompilasi oleh tim berbeda
void *max_notional_limit; // Lupa dideklarasikan sebagai static
```
**Pertanyaan Diagnostik:**
1. Bedah secara mekanistis mengapa dynamic linker mengizinkan penimpaan (*overwriting/aliasing*) memori ini tanpa melempar runtime error atau symbol clash warning saat `dlopen()`.
2. Bagaimana memory layout kedua variabel tersebut bersinggungan di runtime?
3. Langkah hardening toolchain apa (flag kompilasi, visibilitas atribut ELF, atau linker script) yang **wajib** diintegrasikan ke CI/CD pipeline untuk mengeliminasi kerentanan ini secara absolut?

---

### Skenario B: Kerusakan Memori - Pthread Stack Clashing & Silent Page Corruption
Sebuah layanan multi-threaded pemrosesan video berbasis C mengalami *segmentation fault* sporadis dan tidak deterministik pada server dengan utilisasi tinggi. Setiap thread dibuat menggunakan `pthread_create()` dengan atribut default. Investigasi *core dump* menggunakan GDB menunjukkan bahwa *thread stack* menabrak batas alokasi, namun proteksi Linux *Guard Page* gagal memicu `SIGSEGV` seketika; sebaliknya, thread tersebut merusak (*corrupting*) struktur data heap milik thread lain sebelum akhirnya crash di fungsi yang sama sekali tidak berhubungan.

Cuplikan fungsi pada thread target:
```c
void* worker_transcode(void* arg) {
    // Alokasi matriks kompresi frame lokal
    uint8_t frame_transform_matrix[9 * 1024 * 1024]; 
    execute_transform(frame_transform_matrix);
    return NULL;
}
```

**Pertanyaan Diagnostik:**
1. Mengapa alokasi variabel lokal berukuran 9 MB tersebut berhasil melewati (*jump over*) proteksi default *Guard Page* (umumnya berukuran 4 KB) yang dipasang oleh pustaka `pthread`?
2. Jelaskan fenomena eksploitasi/anomali ini ditinjau dari pergerakan register `%rsp` (*Stack Pointer Clashing*).
3. Bagaimana solusi arsitektural yang benar untuk mengalokasikan buffer berukuran besar pada lingkungan thread C, dan bagaimana cara memverifikasi batas stack aman menggunakan API POSIX atau compiler probe flags (`-fstack-clash-protection`)?

---

### Skenario C: Rekayasa Bare-Metal: VMA vs. LMA Mismatch pada Flash/SRAM Loader
Anda ditugaskan mendesain firmware *bootloader* untuk mikrokontroler berbasis ARM Cortex-M/RISC-V tanpa OS (Bare-metal). Flash memory (ROM non-volatile) berada pada alamat `0x08000000`, sedangkan internal SRAM (volatile) berada pada alamat `0x20000000`. Segment `.data` harus disimpan di Flash saat listrik mati, tetapi harus dieksekusi dan dimanipulasi dari SRAM saat runtime demi performa baca-tulis kecepatan tinggi.

Diberikan potongan skrip linker (`linker.ld`):
```ld
SECTIONS
{
    .text : {
        *(.text*)
        *(.rodata*)
    } > FLASH

    .data : {
        _sdata = .;
        *(.data*)
        _edata = .;
    } > SRAM AT > FLASH

    _sidata = LOADADDR(.data);
}
```

**Pertanyaan Diagnostik:**
1. Jelaskan perbedaan mendasar antara **VMA** (*Virtual/Execution Memory Address*) dan **LMA** (*Load Memory Address*) dalam konteks deklarasi `.data : { ... } > SRAM AT > FLASH`.
2. Tuliskan kode C murni tingkat rendah (Low-Level Startup Code / Reset Handler routine) yang mengonsumsi simbol `_sdata`, `_edata`, dan `_sidata` untuk melakukan relokasi memori fisik manual dari Flash ke SRAM sebelum fungsi `main()` dipanggil.
3. Apa yang terjadi jika startup routine lupa menginisialisasi section `.bss` ke nol secara manual di bare-metal environment? Berikan skenario bug logis yang sulit dideteksi jika inisialisasi ini terlewatkan.

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Inspector Segment & Validasi Sekuritas ELF x86_64 (`mini-elfcheck`)

#### Deskripsi Masalah
Sebagai System Engineer, Anda tidak selalu memiliki akses ke utilitas GNU binary (`readelf`, `objdump`, `nm`) pada *minimal stripped environment* (seperti container containerless berbasis Scratch, sistem embedded, atau kernel initial ramdisk). Anda dituntut membuat sebuah tool biner mandiri bernama `mini-elfcheck` menggunakan bahasa C murni. Tool ini harus mampu membaca file biner ELF 64-bit target, mem-parsing strukturnya langsung dari disk, merekonstruksi memory map-nya, serta melakukan audit keamanan biner.

#### Spesifikasi Fungsional & Teknis
Program Anda harus menerima argumen jalur biner target (contoh: `./mini-elfcheck /bin/ls`) dan menghasilkan output komprehensif:

1. **ELF Header Parsing:**
   - Memvalidasi *Magic Bytes* ELF (`0x7F 'E' 'L' 'F'`). Jika tidak valid, terminasi program dengan pesan error terstruktur.
   - Mengidentifikasi arsitektur (harus ELF64), *Endianness* (Little/Big Endian), dan *Entry Point Address* (heksadesimal).

2. **Program Header Table (PHT) Analysis & Memory Layout Reconstruction:**
   - Melakukan iterasi seluruh entri PHT (`Elf64_Phdr`).
   - Menampilkan tabel representasi runtime memory map untuk setiap segment bertipe `PT_LOAD`:
     - Offset File.
     - Target VMA (*Virtual Memory Address*).
     - Ukuran pada File (*File Size*) vs Ukuran pada Memori (*Memory Size*).
     - Proteksi akses flags (`R`, `W`, `E`).
     - *Alignment boundary*.
   - Mengidentifikasi keberadaan Section `.bss` implisit dengan menghitung selisih matematis antara `p_memsz` dan `p_filesz` pada segment `PT_LOAD` data.

3. **Security Posture Audit:**
   - **Check 1: Non-Executable Stack (NX/DEP).** Analisis segment `PT_GNU_STACK`. Periksa apakah flag eksekusi (`PF_X`) aktif. Jika aktif atau jika segment tidak ditemukan, laporkan status: `NX Status: DISABLED (VULNERABLE)`. Jika tidak mengandung `PF_X`, laporkan: `NX Status: ENABLED (SECURE)`.
   - **Check 2: Relocation Read-Only (RELRO).** Deteksi keberadaan segment `PT_GNU_RELRO`. Laporkan apakah biner memiliki kapabilitas RELRO (Partial/Full RELRO baseline).

#### Batasan Implementasi (Constraints)
- Standar bahasa: C11. Toolchain: GCC/Clang pada Linux x86_64.
- Library yang diizinkan: Standar POSIX C Library (`stdio.h`, `stdlib.h`, `stdint.h`, `string.h`, `unistd.h`, `fcntl.h`, `sys/mman.h`, `sys/stat.h`, `elf.h`).
- **Dilarang keras** menggunakan `system()`, `popen()`, atau memanggil utility external seperti `readelf`, `objdump`, atau `exec*`.
- Gunakan *system call* `mmap()` (POSIX) untuk memetakan file biner ke memory space `mini-elfcheck` secara *read-only* (`PROT_READ`), kemudian mapping struct pointer internal ELF64 (`Elf64_Ehdr`, `Elf64_Phdr`) langsung di atas memory-mapped region tersebut.
- Penanganan error wajib absolut: program tidak boleh *crash* (Segmentation Fault/Bus Error) saat diberikan input file corrupt, terpotong (*truncated binary*), atau file non-ELF. Periksa batas panjang file (*bounds checking*) terhadap ukuran struktur header yang diparsing.

#### Expected Output Format
Eksekusi: `./mini-elfcheck /usr/bin/target_binary`
```text
================================================================================
ELF64 ARTIFACT ANALYSIS: /usr/bin/target_binary
================================================================================
[+] Architecture        : ELF64 (Little Endian)
[+] Entry Point Address : 0x0000000000401120
[+] Program Headers     : 11 entries at offset 64

================================================================================
RECONSTRUCTED RUNTIME LOAD SEGMENTS (MEMORY MAP)
================================================================================
Idx  Type     Offset             VirtAddr           PhysAddr           FileSiz    MemSiz     Flg Align
--------------------------------------------------------------------------------
00   LOAD     0x0000000000000000 0x0000000000400000 0x0000000000400000 0x000008b8 0x000008b8 R   0x1000
01   LOAD     0x0000000000001000 0x0000000000401000 0x0000000000401000 0x000002cd 0x000002cd R E 0x1000
02   LOAD     0x0000000000002000 0x0000000000402000 0x0000000000402000 0x00000180 0x00000180 R   0x1000
03   LOAD     0x0000000000002e10 0x0000000000403e10 0x0000000000403e10 0x00000220 0x00000238 RW  0x1000
     └── Implicit .bss Detected: 24 bytes (MemSiz > FileSiz)

================================================================================
SECURITY POSTURE EVALUATION
================================================================================
[*] Exploit Mitigation:
    - NX Stack Protection : ENABLED (PF_X not set in PT_GNU_STACK)
    - RELRO Status        : PRESENT (PT_GNU_RELRO found)
================================================================================
```

---

## 5. Knowledge Check & Checklist

Verifikasi pemahaman konseptual dan kapabilitas teknis Anda sebelum melangkah ke Bab 02. Gunakan instrumen evaluasi mandiri ini secara objektif.

### Saya harus memahami:
- [ ] Siklus hidup lengkap transformasi kode sumber C menjadi biner executable: tokenisasi/ekspansi macro (`cpp`), sintaksis & optimasi representasi intermediate (`cc1`), translasi instruksi mesin assembler (`as`), serta resolusi alamat dan simbol oleh linker (`ld`).
- [ ] Perbedaan fundamental antara *Relocatable Object File* (`.o`), *Shared Object* (`.so`), dan *Executable Binary*.
- [ ] Struktur internal format ELF: Peran Header, Program Header Table (Segment View untuk loader), Section Header Table (Section View untuk linker), serta Symbol Table (`.symtab`, `.dynsym`).
- [ ] Letak, karakteristik mutabilitas, dan siklus hidup variabel dalam segmen-segmen memori virtual: `.text`, `.rodata`, `.data`, `.bss`, Heap, Stack, dan Memory Mapping Area.
- [ ] Perbedaan operasional antara *Virtual Memory Address* (VMA) dan *Load Memory Address* (LMA) pada embedded system linker script.
- [ ] Mekanisme kerja Position Independent Code (PIC/PIE), Global Offset Table (GOT), Procedure Linkage Table (PLT), dan evaluasi Lazy Binding vs Full RELRO.
- [ ] Resolusi ambiguitas simbol: aturan Strong Symbol vs Weak Symbol, tentatif definisi, serta bahaya ODR (*One Definition Rule*) violation pada C.
- [ ] Konvensi ABI AMD64/x86_64: Passing register argumen (`%rdi`, `%rsi`, `%rdx`, dst.), alokasi stack frame, dan signifikansi 16-byte stack boundary alignment.

### Saya tidak perlu menghafal:
- [ ] Nomor opcode heksadesimal individual dari instruksi assembly mesin CPU target (misal: encoding heksadesimal x86 untuk `mov`, `jmp`).
- [ ] Nilai numerik konstan integer konkret dari ELF Struct constants (misal: konstanta heksadesimal untuk `PT_LOAD`, `EI_MAG0`, atau `DT_REL`). Nilai-nilai ini terdefinisi secara kanonikal di `<elf.h>`.
- [ ] Seluruh offset byte spesifik dari ribuan field internal struktur kernel `task_struct` atau `mm_struct`.
- [ ] Sintaks mikro dari ratusan opsi obscure GNU Linker (`ld`), selama Anda memahami konsep dasarnya dan tahu flag penting arsitekturalnya (seperti `-z relro`, `-z now`, `-pie`, `-fPIC`, `-static`).

### Saya harus bisa melakukan:
- [ ] Memeriksa, mengekstrak, dan menganalisis struktur header, section, segment, dan relocations file biner menggunakan utilitas diagnosa biner: `readelf -h -l -S`, `objdump -d -t`, `nm -C`, dan `size`.
- [ ] Memetakan proses runtime yang sedang berjalan ke VMA-nya dengan menginspeksi direktori procfs Linux: `/proc/<PID>/maps` dan `/proc/<PID>/smaps`.
- [ ] Menulis file Linker Script (`.ld`) kustom minimalis untuk sistem bare-metal yang mengatur penempatan segment memori di Flash dan RAM.
- [ ] Mendiagnosis akar masalah kerusakan memori tingkat lanjut seperti *stack-clashing*, tabrakan simbol dinamis (*symbol interception*), atau *relocation truncations* menggunakan GDB dan address sanitizers (`-fsanitize=address`).
- [ ] Mengonfigurasi flag kompilasi GCC/Clang secara tepat untuk menghasilkan biner dengan tingkat proteksi industri: `-fstack-protector-strong`, `-D_FORTIFY_SOURCE=2`, `-fPIE -pie`, `-Wl,-z,relro,-z,now`.