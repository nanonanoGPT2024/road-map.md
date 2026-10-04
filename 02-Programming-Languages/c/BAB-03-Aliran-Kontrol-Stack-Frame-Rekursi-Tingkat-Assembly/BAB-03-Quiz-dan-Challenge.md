# BAB 03: Quiz, Challenge, & Knowledge Check
**Aliran Kontrol, Stack Frame, & Rekursi Tingkat Assembly**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Prosedural ABI dan Register Partitioning
Pada arsitektur System V AMD64 ABI (Linux/POSIX), jelaskan pembagian peran antara *Caller-Saved Registers* (volatile) dan *Callee-Saved Registers* (non-volatile). Sebutkan register mana saja yang termasuk dalam masing-masing kategori untuk passing parameter, dan jelaskan konsekuensi mekanis pada instruksi assembly di fungsi pemanggil (*caller*) dan fungsi yang dipanggil (*callee*) jika sebuah *callee* perlu menggunakan register `RBX` dan `R12`.

### Soal 1.2: Mekanisme Eksekusi Prologue, Epilogue, dan Stack Alignment
Dekomposisikan urutan instruksi standar x86-64 *function prologue* (`push rbp; mov rbp, rsp; sub rsp, N`) dan *epilogue* (`leave; ret`). Mengapa System V ABI mewajibkan *stack pointer* (`RSP`) berada pada batas kelipatan 16-byte (*16-byte aligned*) tepat sebelum instruksi `call` dieksekusi? Apa konsekuensi tingkat CPU (khususnya instruksi SIMD/SSE seperti `movaps`) jika alignment ini dilanggar?

### Soal 1.3: Red Zone pada Arsitektur System V AMD64
Jelaskan konsep alokasi *Red Zone* sebesar 128 byte di bawah `%rsp` pada x86-64. 
- Mengapa kompilator memanfaatkan ruang ini untuk *leaf function* tanpa memodifikasi `%rsp`?
- Mengapa kode kernel sistem operasi, *interrupt service routines* (ISR), atau penanganan sinyal (*signal handlers*) secara eksplisit menonaktifkan *Red Zone* (misalnya menggunakan flag `-mno-red-zone`)?

### Soal 1.4: Transformasi Aliran Kontrol: Jump Table vs Sequential Branching
Kompilator mengonversi struktur `switch-case` dalam C menjadi salah satu dari dua representasi assembly: rangkaian percabangan kondisional (`cmp` / `jcc`) atau *indirect jump* melalui *jump table*. 
- Kriteria densitas dan kuantitas nilai *case* apa yang memicu pembentukan *jump table*?
- Bagaimana CPU branch predictor (khususnya *Indirect Branch Predictor*) menangani eksekusi *jump table* dibandingkan dengan *Branch Target Buffer* (BTB) pada sequential conditional branches?

### Soal 1.5: Rekursi vs Tail Call Optimization (TCO)
Jelaskan perbedaan representasi stack frame antara rekursi linier dan rekursi ekor (*tail recursion*). Kondisi invariabel apa pada *activation record* yang harus dipenuhi oleh fungsi C agar kompilator (pada level optimasi `-O2` atau `-O3`) dapat mengubah instruksi `call` rekursif menjadi instruksi unconditional jump (`jmp`), sehingga mereduksi kompleksitas ruang dari $O(N)$ menjadi $O(1)$?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Frame Pointer Elimination dan DWARF Call Frame Information (CFI)
Saat kompilasi dilakukan dengan flag `-fomit-frame-pointer`, register `%rbp` dibebaskan menjadi general-purpose register, dan fungsi tidak lagi membentuk *base pointer link*. 
- Bagaimana debugger seperti GDB atau profiler berbasis eBPF mampu merekonstruksi *call stack trace* (stack unwinding) secara presisi tanpa keberadaan `%rbp`?
- Jelaskan peran seksi biner `.eh_frame`, instruksi `.cfi_def_cfa_offset`, dan `.cfi_offset` dalam proses rekonstruksi frame virtual tersebut.

### Soal 2.2: Mekanisme Proteksi Stack Canary (`-fstack-protector`)
Analisislah kode assembly di bawah ini yang dihasilkan dengan proteksi SSP (*Stack Smashing Protector*):
```assembly
mov    rax, QWORD PTR fs:0x28
mov    QWORD PTR [rbp-0x8], rax
xor    eax, eax
...    ; [eksekusi bodi fungsi]
mov    rdx, QWORD PTR [rbp-0x8]
sub    rdx, QWORD PTR fs:0x28
jne    .L_stack_chk_fail
```
1. Dari segmen memori mana nilai canary diambil (`fs:0x28`), dan bagaimana OS menginisialisasi nilai tersebut?
2. Mengapa posisi canary diletakkan tepat di antara alokasi variabel lokal bertipe buffer (array/struct) dan *saved base pointer* (`%rbp`) / *return address*?
3. Apa keterbatasan fundamental dari proteksi ini terhadap serangan *arbitrary memory write* yang tidak bersifat linier (misalnya penulisan melalui indeks array yang tidak tervalidasi: `arr[index] = val`)?

### Soal 2.3: Anatomi Alokasi Dinamis pada Stack: VLA dan `alloca()`
Ketika fungsi mendeklarasikan *Variable Length Array* (VLA) atau memanggil `alloca()`, ukuran alokasi baru diketahui saat *runtime*.
- Bagaimana instruksi assembly menyesuaikan `%rsp` secara dinamis di tengah eksekusi fungsi?
- Mengapa kehadiran VLA atau `alloca()` memaksa kompilator mempertahankan `%rbp` (*frame pointer*) meskipun flag `-fomit-frame-pointer` diaktifkan?
- Apa dampak penggunaan VLA terhadap *stack probing* ketika alokasi melebihi ukuran halaman memori virtual (*page boundary*)?

### Soal 2.4: Diagnostik Stack Overflow dan Alternatif Signal Stack (`sigaltstack`)
Ketika sebuah fungsi rekursif melampaui batas alokasi stack yang dialokasikan OS (`RLIMIT_STACK`), CPU memicu *page fault* pada guard page, yang diterjemahkan kernel menjadi sinyal `SIGSEGV`. 
- Mengapa aplikasi yang memasang *signal handler* standar untuk `SIGSEGV` melalui `signal(SIGSEGV, handler)` langsung mengalami *crash* seketika (*double fault*) tanpa sempat mengeksekusi handler tersebut saat terjadi stack overflow?
- Jelaskan implementasi perbaikan menggunakan syscall `sigaltstack()` dan flag `SA_ONSTACK` pada `sigaction` untuk memungkinkan *graceful diagnostics dump* saat stack kolaps.

### Soal 2.5: Kegagalan Tail Call Optimization (TCO) Silang-Arsitektur
Perhatikan fungsi C berikut:
```c
typedef struct {
    int data[16];
} LargeData;

LargeData transform(LargeData in);

LargeData process(LargeData x) {
    // Logika transformasi
    return transform(x);
}
```
Meskipun pemanggilan `transform(x)` berada tepat pada posisi return (posisi ekor), jelaskan secara detail tingkat ABI mengapa kompilator x86-64 kerap **gagal** melakukan Tail Call Optimization (TCO) pada kode ini dan tetap mempertahankan pembentukan stack frame baru serta instruksi `call`.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Crash Terputus-putus pada Pipeline Pemrosesan Citra Berbasis SIMD
**Konteks Sistem:**  
Sebuah modul decoding video berkinerja tinggi ditulis dalam C dan di-compile menggunakan GCC dengan flag `-O3 -mavx2`. Modul ini mengimplementasikan pemrosesan multithreading di mana setiap thread diinisialisasi menggunakan `pthread_create()`. Fungsi pemrosesan memanggil fungsi eksternal yang ditulis dalam assembly manual untuk melakukan kalkulasi vektor menggunakan instruksi `vmovaps` (Vector Move Aligned Packed Single-Precision).

**Insiden:**  
Program berjalan normal pada sebagian besar alur, namun mengalami crash mendadak dengan sinyal `SIGSEGV` pada instruksi `vmovaps ymm0, [rsp + 32]` hanya ketika fungsi tersebut dipanggil melalui callback antarmuka bahasa lain (C Foreign Function Interface/FFI) atau dari thread yang stack-nya dikustomisasi via `pthread_attr_setstack()`.

**Tugas Diagnostik:**
1. Mengapa instruksi `vmovaps` memicu `SIGSEGV` meskipun alamat memori yang dituju berada dalam rentang valid memori stack aplikasi?
2. Bagaimana Anda memverifikasi nilai register `RSP` saat crash terjadi menggunakan GDB, dan nilai heksadesimal apa pada digit terakhir `RSP` yang membuktikan akar masalah tersebut?
3. Langkah mitigasi apa yang harus diterapkan pada deklarasi fungsi C, atribut kompilator (`__attribute__((force_align_arg_pointer))`), atau pembuatan thread stack untuk menjamin alignment 32-byte untuk instruksi AVX?

---

### Skenario B: Kerusakan Data Senyap (*Silent Data Corruption*) pada Embedded RTOS
**Konteks Sistem:**  
Sebuah sistem kontrol industri berbasis ARM Cortex-M4 menjalankan RTOS dengan ruang memori terbatas. Setiap *task* diberikan ukuran stack statis sebesar 2 KB. Sebuah algoritma pencarian pathfinding berbasis rekursi DFS (*Depth-First Search*) diimplementasikan untuk memetakan rute logistik lokal.

**Insiden:**  
Sistem tidak pernah mengalami HardFault atau crash eksplisit. Namun, sensor dan aktuator yang dikontrol oleh task lain yang lokasinya berdekatan secara memori melaporkan nilai yang terkorupsi secara acak setiap kali DFS mencapai kedalaman di atas 25 level. Investigasi awal menunjukkan tidak ada pointer liar (*dangling pointers*) di sisi aplikasi.

**Tugas Diagnostik:**
1. Jelaskan bagaimana *stack overflow* pada arsitektur tanpa MMU (seperti mayoritas mikrokontroler Cortex-M) dapat menimpa struktur data task lain (*Task Control Block* atau stack task tetangga) tanpa memicu fault hardware secara instan.
2. Jelaskan mekanisme perangkat keras MPU (Memory Protection Unit) yang dapat dikonfigurasi untuk mencegah fenomena *silent overwrite* ini melalui konfigurasi *Guard Region*.
3. Jika MPU tidak tersedia, rancang mekanisme deteksi perangkat lunak berbasis *Stack Watermarking* dan jelaskan bagaimana Anda mengukur konsumsi stack aktual maksimum (*high-water mark*) dari algoritma rekursif tersebut.

---

### Skenario C: Bottleneck Latensi pada Parser JSON Skala Masif Akibat Branch Misprediction
**Konteks Sistem:**  
Sebuah microservice trading frekuensi tinggi (HFT) memproses payload JSON heterogen menggunakan recursive descent parser yang ditulis dalam C standar. Loop utama parser menggunakan konstruksi `switch(*cursor)` besar dengan 24 *cases* untuk menangani token grammar JSON.

**Insiden:**  
Analisis menggunakan Linux `perf` menunjukkan metrik:
```text
  18.42%  parser_core  [.] parse_value
   8.15%  branch-misses:u  # 24.12% of all branches
```
Latensi p99 berada pada 180 mikrosekon, melampaui SLA sebesar 50 mikrosekon. Branch misprediction pada jump table/switch statement diidentifikasi sebagai bottleneck utama yang menyebabkan pipeline flush pada CPU secara konstan.

**Tugas Diagnostik:**
1. Mengapa *indirect jump* (`jmp *rax`) yang dihasilkan oleh jump table switch statement sangat rentan mengalami *branch misprediction* ketika memproses payload data yang acak dan heterogen?
2. Evaluasi trade-off arsitektural antara:
   - Mempertahankan `switch-case` jump table.
   - Refactoring menjadi *Direct Threaded Code* menggunakan ekstensi GCC *Labels as Values* (`void *dispatch_table[] = {&&do_num, &&do_str, ...}`).
   - Mengubah algoritma rekursif menjadi pendekatan berbasis tabel state non-rekursif (*Iterative Table-Driven State Machine* dengan explicit stack).
3. Bagaimana modifikasi layout memori data struktur parser dapat meningkatkan efisiensi instruction cache (I-cache) dan meminimalkan penalty pipeline CPU?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekonstruksi Call Stack & Runtime Stack Frame Inspector Tanpa Library Eksternal

#### Deskripsi Masalah:
Dalam pengembangan sistem kritis (*mission-critical systems*), ketergantungan pada pustaka runtime eksternal seperti `libunwind` atau glibc `backtrace()` sering kali dilarang karena alokasi memori dinamis tersembunyi (*hidden malloc*), signal-unsafe behavior, atau overhead binary footprint. Anda diminta mengimplementasikan sistem pelacak stack manual (*Bare-metal Stack Walker & Profiler*) mandiri dalam C murni dan inline assembly x86-64 yang tahan terhadap optimasi kompilator.

#### Kebutuhan Fungsional (Requirements):
1. **Fungsi `inspect_call_stack()`:**
   - Menelusuri seluruh *chain* stack frame aktif dari titik pemanggilan hingga fungsi `main`.
   - Mengambil dan mencetak:
     - Nomor kedalaman frame (Frame Index).
     - Alamat virtual *Base Pointer* (`RBP`) dan *Stack Pointer* (`RSP`) masing-masing frame.
     - Ukuran stack frame aktual dalam satuan bytes.
     - *Return Address* yang tersimpan di stack.
2. **Rekursi Terkendali dengan TCO Verification:**
   - Buat algoritma perhitungan barisan matematika (misal: faktorial atau permutasi modular) dalam dua varian:
     - `func_standard_recursive`: Rekursi biasa yang **memaksa** pembentukan stack frame baru di setiap level.
     - `func_tco_recursive`: Rekursi ekor yang **harus** dioptimasi menjadi satu frame konstan via tail call optimization.
   - Panggil `inspect_call_stack()` di dalam kedalaman rekursi ke-5 untuk membuktikan keberadaan 5 frame berbeda pada varian standar, dan hanya 1 frame aktif pada varian TCO.
3. **Assembly-Level Invariant Assertion:**
   - Tulis macro inline assembly `ASSERT_STACK_ALIGNED_16()` yang mengecek apakah `%rsp` berada pada batas alignment 16-byte. Jika tidak aligned, cetak peringatan fatal dan hentikan eksekusi (*abort*).

#### Batasan Teknis (Constraints):
- **Standar Bahasa:** C11 murni.
- **Kompilator:** GCC atau Clang pada x86-64 Linux.
- **Dilarang Keras:** 
  - Menggunakan `<execinfo.h>` (`backtrace()`, `backtrace_symbols()`).
  - Menggunakan fungsi bawaan `__builtin_return_address()` atau `__builtin_frame_address()`. Penelusuran stack harus dilakukan secara manual melalui pembacaan dereferensi pointer ke memory stack.
- **Opsi Kompilasi:** Wajib bekerja dengan flag kompilasi:
  ```bash
  gcc -O2 -fno-omit-frame-pointer -no-pie bab03_challenge.c -o bab03_challenge
  ```
  *(Penggunaan `-fno-omit-frame-pointer` diwajibkan untuk menjamin persistensi RBP chain).*

#### Expected Output:
Eksekusi program harus menghasilkan output deterministik terstruktur menyerupai format berikut:

```text
================================================================================
STACK INSPECTION: STANDARD RECURSION (Depth: 5)
================================================================================
Frame  Level | Base Pointer (RBP)  | Stack Pointer (RSP) | Frame Size | Return Address     
--------------------------------------------------------------------------------
[00] CURRENT | 0x7ffd5c32a100      | 0x7ffd5c32a0e0      |   32 bytes | 0x0000000000401248
[01] CALLER  | 0x7ffd5c32a130      | 0x7ffd5c32a110      |   48 bytes | 0x0000000000401290
[02] CALLER  | 0x7ffd5c32a170      | 0x7ffd5c32a140      |   48 bytes | 0x0000000000401290
[03] CALLER  | 0x7ffd5c32a1b0      | 0x7ffd5c32a180      |   48 bytes | 0x0000000000401290
[04] CALLER  | 0x7ffd5c32a1f0      | 0x7ffd5c32a1c0      |   48 bytes | 0x0000000000401290
[05] MAIN    | 0x7ffd5c32a230      | 0x7ffd5c32a200      |   64 bytes | 0x00007f9c8f2b3083
================================================================================
Stack alignment check at Frame 0: ALIGNED (RSP % 16 == 0)

================================================================================
STACK INSPECTION: TAIL CALL OPTIMIZED (Depth: 5)
================================================================================
Frame  Level | Base Pointer (RBP)  | Stack Pointer (RSP) | Frame Size | Return Address     
--------------------------------------------------------------------------------
[00] CURRENT | 0x7ffd5c32a100      | 0x7ffd5c32a0e0      |   32 bytes | 0x0000000000401350
[01] MAIN    | 0x7ffd5c32a230      | 0x7ffd5c32a200      |   64 bytes | 0x00007f9c8f2b3083
================================================================================
Verification: TCO Successfully Eliminated Intermediate Stack Frames!
```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memvalidasi kematangan penguasaan materi pada bab ini secara objektif sebelum beralih ke rekayasa memori tingkat lanjut.

### Saya harus memahami:
- [ ] Mekanisme transit register parameter (`RDI`, `RSI`, `RDX`, `RCX`, `R8`, `R9`) dan overflow parameter via stack pada System V AMD64 ABI.
- [ ] Perbedaan esensial fungsional antara *stack frame base pointer* (`RBP`) sebagai penanda batas konstan dan *stack pointer* (`RSP`) yang bersifat dinamis.
- [ ] Struktur hierarkis memori stack frame: *Function Parameters* $\rightarrow$ *Return Address* $\rightarrow$ *Saved Frame Pointer* $\rightarrow$ *Local Variables* $\rightarrow$ *Spill Slots*.
- [ ] Peran dan batasan arsitektur *Red Zone* (128 bytes) dalam mempercepat siklus eksekusi leaf functions.
- [ ] Perilaku branch predictor CPU (BTB vs Indirect Predictor) terhadap aliran kontrol statis, percabangan kondisional, dan jump tables.
- [ ] Dampak pelanggaran alignment 16-byte pada `%rsp` terhadap instruksi SSE/AVX dan panggilan fungsi standar library.
- [ ] Hubungan antara rekursi tak terbatas (*unbounded recursion*), ukuran Virtual Memory Page, Guard Page OS, dan pemicuan sinyal `SIGSEGV`.

### Saya tidak perlu menghafal:
- [ ] Representasi biner (*opcode hex encoding*) individual dari instruksi percabangan assembly (misal: opcode byte untuk `jne`, `jg`, atau `callq`).
- [ ] Sintaks mikro format DWARF Call Frame Information (`.cfi_*` directives) secara mendetail di luar pemahaman konsep pemetaannya.
- [ ] Konvensi register Windows 64-bit ABI (`RCX`, `RDX`, `R8`, `R9` + shadow store) saat bekerja secara spesifik pada platform System V POSIX (cukup memahami perbedaannya ada).

### Saya harus bisa melakukan:
- [ ] Melakukan disassembling file objek C (`objdump -d -M intel` atau GDB `disassemble /m`) dan memetakan struktur kode tingkat tinggi C ke baris instruksi assembly pembentuknya.
- [ ] Menentukan ukuran stack frame sebuah fungsi secara manual hanya dengan menganalisis instruksi *prologue* dan alokasi lokalnya.
- [ ] Mendiagnosis bug kerusakan memori (*stack corruption*) akibat buffer overflow menggunakan analisis register GDB (`info registers`, `x/gx $rsp`, `bt`).
- [ ] Merancang algoritma rekursif yang memenuhi kriteria *tail-call position* dan memvalidasi emisinya menjadi instruksi jump tanpa penambahan frame pada level biner.
- [ ] Mengonfigurasi `sigaltstack()` untuk menangani dan mendokumentasikan crash insiden akibat Stack Overflow secara aman tanpa memicu *double fault*.