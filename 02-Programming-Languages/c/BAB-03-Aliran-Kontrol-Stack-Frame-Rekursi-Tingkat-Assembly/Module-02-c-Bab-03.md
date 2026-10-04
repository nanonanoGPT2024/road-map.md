# BAB 03: Aliran Kontrol, Stack Frame, & Rekursi Tingkat Assembly
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan memiliki kemampuan:
- **Menganalisis & Merekayasa Stack Frame:** Menginspeksi anatomi stack frame x86_64 (System V AMD64 ABI vs. Microsoft x64) pada tingkat register, mencakup *prologue*, *epilogue*, alokasi variabel lokal, *stack alignment* (16-byte boundary), dan *red zone*.
- **Mengontrol Optimasi Kompiler:** Membedah dan mengonfigurasi mekanisme *Tail Call Optimization* (TCO) dan *Frame Pointer Omission* (`-fomit-frame-pointer`), serta memahami trade-off visibilitas debugging (*profiling*, eBPF, stack unwinding) versus ketersediaan register umum.
- **Mitigasi Eksploitasi Memori Stack:** Menganalisis cara kerja *Stack Smashing Protector* (SSP/Canary), deteksi *stack exhaustion*, bahaya alokasi dinamis pada stack (`alloca`, C99 Variable-Length Arrays / VLA), dan mitigasinya menggunakan batasan kedalaman rekursi eksplisit atau *trampoline pattern*.
- **Membangun Arsitektur Non-Local Jumps:** Mengimplementasikan mesin *cooperative multitasking* (green threads/fibers) tingkat produksi berbasis `setjmp`/`longjmp` dengan isolasi memori execution context.

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, engineer harus menguasai:
1. Pemahaman mendalam tentang pointer C, *type casting*, dan alokasi memori heap (`malloc`, `free`).
2. Familiaritas dengan register dasar arsitektur x86_64 (`rax`, `rbx`, `rcx`, `rdx`, `rsi`, `rdi`, `rbp`, `rsp`, `r8`–`r15`, `rip`).
3. Penggunaan toolchain GNU/Clang (`gcc`, `clang`, `gdb`, `objdump`, `readelf`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Calling Conventions & Register Preservation
Kompilasi kode C menjadi assembly diatur oleh *Application Binary Interface* (ABI). Standar dominan sistem operasi modern adalah:
- **System V AMD64 ABI** (Linux, macOS, BSD): Enam argumen bilangan bulat/pointer pertama dilewatkan berturut-turut melalui register `%rdi`, `%rsi`, `%rdx`, `%rcx`, `%r8`, `%r9`. Argumen floating-point melalui `%xmm0`–`%xmm7`. Argumen sisanya didorong ke stack dalam urutan *right-to-left*.
- **Microsoft x64 ABI** (Windows): Empat argumen pertama dilewatkan via `%rcx`, `%rdx`, `%r8`, `%r9`. Membutuhkan *shadow space* (32 byte) yang dialokasikan oleh pemanggil (*caller*) di atas stack sebelum instruksi `call`.

Register dikategorikan menjadi dua jenis tanggung jawab pelestarian:
1. **Callee-saved (Preserved Registers):** `%rbx`, `%rsp`, `%rbp`, `%r12`, `%r13`, `%r14`, `%r15`. Jika fungsi yang dipanggil (*callee*) ingin menggunakan register ini, ia **wajib** menyimpannya ke stack dan mengembalikannya ke nilai semula sebelum mengeksekusi instruksi `ret`.
2. **Caller-saved (Scratch Registers):** `%rax`, `%rcx`, `%rdx`, `%rsi`, `%rdi`, `%r8`, `%r9`, `%r10`, `%r11`. Nilai pada register ini dapat ditimpa secara bebas oleh *callee*. Jika *caller* memerlukan nilainya setelah pemanggilan, *caller* harus menyimpannya sebelum memanggil fungsi.

#### 3.2 Anatomi Stack Frame & Alignment
Sesuai System V ABI, stack tumbuh ke bawah (dari alamat memori tinggi ke rendah). Sebelum instruksi `call` dieksekusi, nilai `%rsp` harus memenuhi kondisi `(%rsp + 8) % 16 == 0`. Ketika `call` dieksekusi, CPU mendorong *Return Address* (8 byte) ke stack, sehingga pada saat memasuki fungsi *callee*, `%rsp` teralisasi tepat pada batas kelipatan 16-byte (`%rsp % 16 == 0`). Kegagalan menjaga *16-byte stack alignment* ini akan memicu *General Protection Fault* (GPF / SIGSEGV) saat instruksi SIMD (SSE/AVX seperti `movaps`) dieksekusi.

**Red Zone (AMD64 System V):**
Wilayah 128 byte di bawah `%rsp` (`-128(%rsp)` hingga `-1(%rsp)`) dialokasikan khusus untuk fungsi *leaf* (fungsi yang tidak memanggil fungsi lain). Kompiler dapat menggunakan ruang ini untuk menyimpan variabel lokal sementara tanpa perlu memodifikasi penunjuk stack (`sub $n, %rsp`), sehingga menghemat clock cycles instruksi `sub` dan `add`. Namun, interupsi perangkat keras atau sinyal OS kernel dapat menulis ke area ini sewaktu-waktu jika fungsi *leaf* tidak berjalan di ring level yang terlindungi.

```
       Alamat Tinggi
  +-----------------------+
  | Argument N            |
  | ...                   |
  | Argument 7            |
  +-----------------------+  <-- [Sebelum CALL: RSP % 16 == 8]
  | Return Address (RIP)  |  <-- Didorong otomatis oleh instruksi CALL (8 byte)
  +-----------------------+  <-- [Setelah CALL: RSP % 16 == 0]
  | Saved RBP             |  <-- Prologue: push %rbp (jika frame pointer aktif)
  +-----------------------+  <-- Base Pointer (RBP baru) menunjuk ke sini
  | Stack Canary (Guard)  |  <-- Disisipkan oleh SSP (-fstack-protector-strong)
  +-----------------------+
  | Local Variables       |
  | & Spill Slots         |
  +-----------------------+
  | Callee-saved Regs     |  <-- rbx, r12-r15 (jika digunakan)
  +-----------------------+  <-- Stack Pointer saat ini (%rsp)
  |      Red Zone         |
  |      (128 bytes)      |  <-- Valid untuk leaf functions (hanya System V AMD64)
  +-----------------------+
       Alamat Rendah
```

#### 3.3 Stack Smashing Protector (Canary) Internals
Ketika bendera kompilasi `-fstack-protector-strong` diaktifkan, kompiler menyisipkan nilai rahasia acak (*canary*) yang diambil dari *Thread Local Storage* (`%fs:0x28` pada Linux x86_64) tepat sebelum *Saved RBP* dan *Return Address*. Sebelum fungsi mengeksekusi instruksi `ret`, nilai *canary* di stack dibandingkan kembali dengan `%fs:0x28`. Jika terjadi *buffer overflow* yang merusak data di stack, nilai *canary* akan berubah, instruksi perbandingan akan gagal, dan fungsi seketika memanggil `__stack_chk_fail()` untuk menghentikan program (`SIGABRT`), mencegah eksploitasi eksekusi kode acak.

#### 3.4 Tail Call Optimization (TCO)
Ketika sebuah fungsi mengembalikan hasil pemanggilan fungsi lain secara langsung (tanpa komputasi tambahan setelah panggilan tersebut), kompiler dengan optimasi (`-O2` atau `-O3`) tidak akan menghasilkan instruksi `call`. Kompiler akan:
1. Menimpa argumen fungsi saat ini dengan argumen fungsi baru.
2. Membersihkan stack frame saat ini (*epilogue* parsial).
3. Mengeksekusi instruksi `jmp` langsung ke fungsi tujuan.

Hasilnya, penggunaan stack berubah dari $O(N)$ menjadi $O(1)$, mencegah *stack overflow* pada algoritma rekursif kontinu.

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan di Arsitektur Enterprise? | Apa Dampak Kegagalannya? |
| :--- | :--- | :--- |
| **Frame Pointer (`-fno-omit-frame-pointer`)** | Memungkinkan *stack unwinding* berbiaya rendah dan deterministik secara *real-time* oleh kernel profiler (Linux perf, eBPF/BCC, DTrace) tanpa parsing DWARF `.eh_frame` yang lambat. | CPU profiling overhead melonjak tajam; *flame graph* produksi menghasilkan trace terputus atau tidak lengkap (*broken callstacks*). |
| **Explicit Depth Guard vs. Recursion** | Rekursi yang bergantung pada kedalaman input pengguna (misal: JSON parsing, traversal pohon) dapat menghabiskan stack default Linux (biasanya 8MB) atau thread stack (2MB/128KB). | *Stack Overflow* instan (`SIGSEGV`), membuat aplikasi crash tanpa kesempatan menangani graceful shutdown, memicu celah DoS. |
| **Penghapusan VLA / `alloca`** | VLA mengalokasikan memori pada stack saat runtime berdasarkan variabel non-konstan. Memori stack tidak memiliki mekanisme pemeriksaan batas dinamis layaknya heap. | Menginput angka masif memindahkan `%rsp` melewati batas guard page OS, menyebabkan *Stack Clash vulnerability* (CVE-2017-1000364). |
| **Context Switching (`setjmp`/`longjmp`)** | Pondasi untuk *user-level fibers/coroutines* yang memungkinkan jutaan koneksi I/O konkuren tanpa overhead alokasi thread OS dan kernel-mode transition. | Salah mengelola register terkorupsi atau stack invalid menyebabkan korupsi memori diam-diam (*silent corruption*) dan *undefined behavior*. |

---

### 5. How (Workflow Detail)

Alur eksekusi sebuah pemanggilan fungsi dari C ke Assembly:

```
[Tahap 1: Caller-Side Evaluation]
  1. Komputasi argumen.
  2. Alokasikan register: Arg1->%rdi, Arg2->%rsi, Arg3->%rdx, Arg4->%rcx, Arg5->%r8, Arg6->%r9.
  3. Sisanya (jika > 6) di-push ke stack secara terbalik (Right-to-Left).
  4. Eksekusi `call <function_label>`.
     -> CPU otomatis: Push %rip (alamat instruksi berikutnya), Jump ke target.

[Tahap 2: Callee-Side Prologue]
  1. Push %rbp               ; Simpan frame pointer caller sebelumnya.
  2. Mov %rsp, %rbp          ; Tetapkan frame pointer saat ini.
  3. Sub $N, %rsp            ; Alokasikan N byte untuk variabel lokal (mempertahankan 16-byte alignment).
  4. Mov %fs:0x28, %rax      ; Ambil canary dari TLS.
  5. Mov %rax, -8(%rbp)      ; Simpan canary di stack.
  6. Push register Callee-saved (%rbx, %r12-%r15) jika dimodifikasi.

[Tahap 3: Callee Body Execution]
  - Operasi logika, manipulasi memori lokal via offset RBP (contoh: `-0x10(%rbp)`).

[Tahap 4: Callee-Side Epilogue]
  1. Pop register Callee-saved dalam urutan terbalik.
  2. Mov -8(%rbp), %rax      ; Baca kembali canary dari stack.
  3. Xor %fs:0x28, %rax      ; Periksa apakah canary berubah.
  4. Jne __stack_chk_fail    ; Jika berubah, trigger abort!
  5. Mov %rbp, %rsp          ; Lepas alokasi lokal frame.
  6. Pop %rbp                ; Kembalikan RBP milik caller.
  7. Ret                     ; Pop RIP dari stack dan lompat kembali ke Caller.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Stack Frame Sebagai Meja Kerja Kontrak
Bayangkan Anda adalah teknisi (fungsi *Caller*). Ketika Anda meminta asisten (fungsi *Callee*) mengerjakan tugas:
1. Anda menulis instruksi pada formulir kerja dan meletakkan tiket panggilan di atas baki (register `%rdi`–`%r9`).
2. Asisten datang, mengambil selembar kertas catatan, mencatat posisi pekerjaan Anda (*Return Address* dan `%rbp`), lalu menempelkan stempel segel keamanan rahasia (*Canary*).
3. Asisten membersihkan meja kerjanya sendiri untuk meletakkan alat-alatnya (*alokasi stack lokal*).
4. Jika asisten cerdas dan pekerjaannya adalah tugas murni delegasi lanjutan (*Tail Call*), ia tidak membuka meja kerja baru; ia langsung membuang catatan sementaranya, menaruh berkas baru ke baki, dan langsung memanggil asisten berikutnya (*Jump*) tanpa menyimpan riwayatnya sendiri.
5. Setelah selesai, ia memeriksa apakah segel keamanan rusak. Jika utuh, ia mengembalikan posisi meja kerja teknisi sebelumnya, membaca tiket kepulangan, lalu kembali.

#### Diagram Transisi Stack: Rekursi Naif vs. Tail Call Optimization (TCO)

```
Rekursif Naif (Stack Tumbuh O(N)):
Level 0:  [ Frame: fact(3) | ret_to_main | n=3 ]
               |
Level 1:  [ Frame: fact(2) | ret_to_fact | n=2 ]  <- Memori bertambah
               |
Level 2:  [ Frame: fact(1) | ret_to_fact | n=1 ]  <- Memori bertambah
               |
Level 3:  [ Frame: fact(0) | ret_to_fact | n=0 ]  <- RISIKO STACK OVERFLOW!

Tail Call Optimization (Stack Konstan O(1)):
Step 1:   [ Frame: fact_tr(3, acc=1)   | ret_to_main ]
               | (Register diupdate: rdi=2, rsi=3, lalu JMP)
Step 2:   [ Frame: fact_tr(2, acc=3)   | ret_to_main ]  <- Frame yang sama ditimpa!
               | (Register diupdate: rdi=1, rsi=6, lalu JMP)
Step 3:   [ Frame: fact_tr(1, acc=6)   | ret_to_main ]  <- Tidak ada pertumbuhan stack!
               | (Register diupdate: rdi=0, rsi=6, lalu JMP)
Step 4:   [ Frame: fact_tr(0, acc=6)   | ret_to_main ]  <- Langsung RET ke main
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Analisis Disassembly Rekursi vs. TCO
Simpan kode berikut sebagai `recursion_asm.c`:

```c
#include <stdint.h>

// Rekursi standar: Bukan tail call karena ada operasi perkalian SETELAH pemanggilan
uint64_t factorial_naive(uint64_t n) {
    if (n <= 1) return 1;
    return n * factorial_naive(n - 1);
}

// Tail-recursive: Pemanggilan fungsi adalah ekspresi terakhir murni
uint64_t factorial_tail(uint64_t n, uint64_t acc) {
    if (n <= 1) return acc;
    return factorial_tail(n - 1, n * acc);
}
```

Kompilasi dengan inspeksi assembly Intel syntax:
```bash
gcc -O2 -S -masm=intel -fno-stack-protector recursion_asm.c -o recursion_asm.s
```

Potongan hasil perbandingan assembly pada `recursion_asm.s`:
```nasm
# --- factorial_naive (Stack membesar, ada instruksi CALL & PUSH) ---
factorial_naive:
    cmp     rdi, 1
    jbe     .Lbase_naive
    push    rbx                 # Callee-saved: simpan n di stack
    mov     rbx, rdi            # Simpan n ke rbx
    lea     rdi, [rdi-1]        # Argumen n - 1
    call    factorial_naive     # Recursive CALL: menekan RSP
    imul    rax, rbx            # Perkalian terjadi SETELAH return
    pop     rbx                 # Restore rbx
    ret
.Lbase_naive:
    mov     eax, 1
    ret

# --- factorial_tail (Dioptimasi menjadi loop! Tanpa CALL, tanpa PUSH) ---
factorial_tail:
    mov     rax, rsi            # rax = acc
    cmp     rdi, 1
    jbe     .Lbase_tail
.Lloop_tail:
    imul    rax, rdi            # acc = acc * n
    sub     rdi, 1              # n = n - 1
    cmp     rdi, 1
    jne     .Lloop_tail         # JMP langsung, stack frame tidak pernah bertambah
.Lbase_tail:
    ret
```

#### 7.2 Practical Example: Fiber Engine Menggunakan `setjmp`/`longjmp`
Implementasi mesin *cooperative fibers* dengan stack terisolasi di heap, mengilustrasikan manipulasi manual context register dan kontrol alur non-linear.

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <setjmp.h>
#include <stdbool.h>

#define FIBER_STACK_SIZE (64 * 1024) // 64 KB heap stack per fiber
#define MAX_FIBERS 4

typedef enum {
    FIBER_DEAD,
    FIBER_READY,
    FIBER_RUNNING
} fiber_state_t;

typedef struct {
    jmp_buf env;
    void (*entry)(void);
    uint8_t *stack;
    fiber_state_t state;
} fiber_t;

static fiber_t g_fibers[MAX_FIBERS];
static int g_current_fiber = -1;
static jmp_buf g_sched_env;

// Yield eksekusi kembali ke scheduler
void fiber_yield(void) {
    if (setjmp(g_fibers[g_current_fiber].env) == 0) {
        longjmp(g_sched_env, 1);
    }
}

// Wrapper trampoline untuk menjalankan fungsi fiber lalu menandai selesai
static void fiber_trampoline(void) {
    g_fibers[g_current_fiber].entry();
    g_fibers[g_current_fiber].state = FIBER_DEAD;
    longjmp(g_sched_env, 1);
}

// Inisialisasi fiber baru dengan memodifikasi SP register di dalam jmp_buf
bool fiber_create(int id, void (*func)(void)) {
    if (id < 0 || id >= MAX_FIBERS) return false;
    
    g_fibers[id].stack = (uint8_t *)malloc(FIBER_STACK_SIZE);
    if (!g_fibers[id].entry && !g_fibers[id].stack) return false;

    g_fibers[id].entry = func;
    g_fibers[id].state = FIBER_READY;

    // Inisialisasi jmp_buf awal
    if (setjmp(g_fibers[id].env) == 0) {
        /*
         * MANIPULASI STACK POINTER TINGKAT ASSEMBLY (x86_64 System V ABI):
         * Pada glibc x86_64, jmp_buf menyimpan rsp pada index JB_RSP (umumnya index 6).
         * Stack x86_64 tumbuh ke bawah, maka kita arahkan rsp ke bagian teratas buffer stack.
         * Wajib diselaraskan (16-byte alignment - 8 byte offset untuk simulasi CALL return addr).
         */
        uintptr_t stack_top = (uintptr_t)(g_fibers[id].stack + FIBER_STACK_SIZE);
        stack_top = (stack_top & ~0xFULL) - 8; // Pastikan 16-byte aligned

        #if defined(__x86_64__)
            // Manipulasi internal glibc jmp_buf: index 6 = RSP, index 7 = PC (RIP)
            g_fibers[id].env[0].__jmpbuf[6] = (long)stack_top;
            g_fibers[id].env[0].__jmpbuf[7] = (long)fiber_trampoline;
        #else
            #error "Arsitektur tidak didukung untuk demonstrasi manipulasi direct register ini."
        #endif
    }
    return true;
}

void scheduler_run(void) {
    while (true) {
        bool all_dead = true;
        for (int i = 0; i < MAX_FIBERS; ++i) {
            if (g_fibers[i].state != FIBER_DEAD) {
                all_dead = false;
                g_current_fiber = i;
                g_fibers[i].state = FIBER_RUNNING;

                // Lompat ke konteks fiber
                if (setjmp(g_sched_env) == 0) {
                    longjmp(g_fibers[i].env, 1);
                }
                
                if (g_fibers[i].state != FIBER_DEAD) {
                    g_fibers[i].state = FIBER_READY;
                }
            }
        }
        if (all_dead) break;
    }
}

// Pembersihan resource
void scheduler_cleanup(void) {
    for (int i = 0; i < MAX_FIBERS; ++i) {
        if (g_fibers[i].stack) {
            free(g_fibers[i].stack);
            g_fibers[i].stack = NULL;
        }
    }
}

// Worker routines
void worker_alpha(void) {
    for (int i = 0; i < 3; ++i) {
        printf("[Fiber Alpha] Iterasi %d (Stack Base: %p)\n", i, (void*)&i);
        fiber_yield();
    }
}

void worker_beta(void) {
    for (int i = 0; i < 3; ++i) {
        printf("  [Fiber Beta] Iterasi %d (Stack Base: %p)\n", i, (void*)&i);
        fiber_yield();
    }
}

int main(void) {
    printf("Starting Production Fiber Demonstration...\n");
    fiber_create(0, worker_alpha);
    fiber_create(1, worker_beta);

    scheduler_run();
    scheduler_cleanup();
    printf("All fibers completed execution cleanly.\n");
    return 0;
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Denial of Service (DoS) via Deep JSON/Expression Deserializer
**Latar Belakang:**  
Sebuah payment gateway enterprise memproses jutaan payload API berupa format data tersarang (*nested JSON AST*). Parser yang digunakan mengimplementasikan *Recursive Descent Parsing* standar secara naif:

```c
// Kode Bermasalah (Vulnerable to Stack Overflow via Recursive Descent)
ASTNode* parse_expression(Lexer *lexer) {
    ASTNode *node = malloc(sizeof(ASTNode));
    Token tok = lexer_next(lexer);
    if (tok.type == TOKEN_LPAREN) {
        node->child = parse_expression(lexer); // Rekursi tidak terikat!
        lexer_match(lexer, TOKEN_RPAREN);
    }
    return node;
}
```

**Insiden Produksi:**  
Penyerang mengirimkan payload HTTP sebesar 500 KB yang hanya berisi kurung buka bertingkat ribuan lapis: `((((((((...))))))))`. Setiap *frame* fungsi `parse_expression` mengonsumsi 64 byte memori stack. Pada kedalaman nesting 131.072 lapis, fungsi membutuhkan lebih dari 8 MB memori stack, menghantam halaman *guard page* OS. Aplikasi mati seketika dengan `SIGSEGV` (SEGV_MAPERR), melumpuhkan worker node NGINX/C service tanpa memunculkan log error aplikasi.

**Solusi Arsitektur Produksi (Iterative Parser dengan Heap-based Stack):**  
Parsing rekursif direkayasa ulang menjadi mesin berbasis *State Machine* dengan *Explicit Heap Stack*, dilengkapi pembatasan kedalaman ketat (*Bounded Recursion Guard*).

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>

#define MAX_ALLOWED_DEPTH 1024 // Batas kedalaman aman absolut

typedef struct ParserFrame {
    int state;
    void *ast_context;
} ParserFrame;

typedef struct {
    ParserFrame *frames;
    size_t capacity;
    size_t top;
} ExplicitStack;

ExplicitStack* stack_create(size_t initial_cap) {
    ExplicitStack *s = malloc(sizeof(ExplicitStack));
    if (!s) return NULL;
    s->frames = malloc(sizeof(ParserFrame) * initial_cap);
    if (!s->frames) { free(s); return NULL; }
    s->capacity = initial_cap;
    s->top = 0;
    return s;
}

bool stack_push(ExplicitStack *s, ParserFrame frame) {
    if (s->top >= MAX_ALLOWED_DEPTH) {
        // Mencegah DoS: Mengembalikan status error terkontrol alih-alih crash
        return false;
    }
    if (s->top == s->capacity) {
        size_t new_cap = s->capacity * 2;
        ParserFrame *new_frames = realloc(s->frames, sizeof(ParserFrame) * new_cap);
        if (!new_frames) return false;
        s->frames = new_frames;
        s->capacity = new_cap;
    }
    s->frames[s->top++] = frame;
    return true;
}

bool stack_pop(ExplicitStack *s, ParserFrame *out) {
    if (s->top == 0) return false;
    *out = s->frames[--s->top];
    return true;
}

void stack_free(ExplicitStack *s) {
    if (s) {
        free(s->frames);
        free(s);
    }
}
```

---

### 9. Trade-offs

| Pendekatan Rekursi & Stack Frame | Kelebihan | Kekurangan | Latensi & Kompleksitas Runtime | Rekomendasi Kasus Penggunaan |
| :--- | :--- | :--- | :--- | :--- |
| **Direct Recursion (Naif)** | Sintaksis elegan, mudah diekspresikan secara matematis, kode ringkas. | Rentan *stack overflow* pada input tak terpercaya; overhead alokasi/deallokasi frame stack. | Latensi $O(N)$, Memory $O(N)$ stack space. Crash risk tinggi. | Parsing struktur dengan kedalaman dangkal dan terjamin (misal: Red-Black Tree internal). |
| **Tail Call Optimization (TCO)** | Penggunaan stack konstan ($O(1)$), kecepatan setara perulangan iteratif biasa. | Bergantung penuh pada flag optimasi compiler (`-O2`); rapuh terhadap perubahan kode kecil. | Latensi $O(N)$, Memory $O(1)$. Performa CPU tingkat hardware terbaik. | State machine linier, algoritma matematika sekuensial pada embedded system. |
| **Explicit Heap Stack (Iterative)** | Kebal terhadap ukuran limit stack thread OS; dapat memproses jutaan kedalaman data secara aman. | Memerlukan alokasi heap (`malloc`/`realloc`); kode state machine lebih kompleks (*boilerplate* tinggi). | Latensi sedikit lebih tinggi akibat heap pointer indirection, Memory $O(N)$ di Heap. | Deserializer parser API publik, compiler front-end, JSON/XML parsing berskala enterprise. |
| **Trampoline Execution** | Menghindari stack overflow tanpa menulis ulang algoritma menjadi loop; fungsi me-return wrapper thunk. | Overhead *function pointer indirection* di setiap iterasi; performa cache branch prediction menurun. | Memory $O(1)$ stack, Latensi lebih tinggi (overhead pemanggilan loop eksternal). | Runtime bahasa fungsional yang berjalan di atas C engine (misal: Lisp/Scheme runtime). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Mengembalikan Pointer ke Local Stack Variable
```c
// FATAL ERROR
char* get_temporary_buffer(void) {
    char buffer[256];
    snprintf(buffer, sizeof(buffer), "Transaction-OK");
    return buffer; // PERINGATAN / KESALAHAN FATAL: Mengembalikan pointer stack frame yang segera dihancurkan!
}
```
*Efek:* Data di buffer akan terkorupsi begitu ada fungsi lain yang dipanggil karena frame stack tersebut ditimpa (*use-after-free on stack*).  
*Solusi:* Alokasikan ke heap, minta buffer dialokasikan oleh *caller*, atau gunakan `static _Thread_local` jika thread-safe.

#### 2. Korupsi Register Callee-Saved pada GCC Inline Assembly
```c
// SALAH: Merusak register r12 tanpa memberitahu kompiler
void dangerous_asm(void) {
    __asm__ volatile (
        "mov $0x1337, %%r12\n\t"
        : /* no outputs */
        : /* no inputs */
        : /* Missing "r12" clobber! */
    );
}
```
*Efek:* Caller mengasumsikan `%r12` tidak berubah. Program crash secara acak beberapa fungsi kemudian setelah kembali ke caller.  
*Solusi:* Daftarkan register yang diubah di clobber list: `: "r12"`, atau lakukan `push %r12` dan `pop %r12` di dalam assembly block.

#### 3. Prosedur Debugging Stack Korupsi Menggunakan GDB
Jika terjadi crash akibat kerusakan memori stack:
```bash
# 1. Jalankan aplikasi di bawah GDB
gdb ./my_enterprise_app

# 2. Begitu program crash dengan SIGSEGV, periksa register saat ini
(gdb) info registers rsp rbp rip

# 3. Inspeksi frame dan backtrace
(gdb) backtrace
(gdb) info frame

# 4. Periksa apakah RSP melintasi segmen stack memori sah (/proc/$PID/maps)
(gdb) info proc mappings

# 5. Tampilkan 16 word hexadecimal di atas stack pointer saat ini
(gdb) x/16gx $rsp

# 6. Disassemble instruksi di sekitar program counter
(gdb) disassemble /m
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Enforce Stack Protection:** Selalu kompilasi dengan flag `-fstack-protector-strong` atau `-fstack-protector-all` pada seluruh build release.
- [ ] **Audit Alokasi Stack Kompiler:** Gunakan flag `-Wstack-usage=4096` untuk memperingatkan fungsi yang menggunakan stack lebih dari 4KB.
- [ ] **Larang Variable-Length Arrays (VLA):** Tambahkan flag kompilasi `-Wvla` dan `-Werror=vla`. VLA melewati mekanisme proteksi canary standar dan mempermudah serangan stack exhaustion.
- [ ] **Penyelarasan Stack 16-Byte:** Pastikan fungsi hand-written assembly menjaga alignment `(%rsp + 8) % 16 == 0` sebelum instruksi `call`.
- [ ] **Audit Frame Pointer untuk Observabilitas:** Gunakan `-fno-omit-frame-pointer` pada target server produksi modern agar *profiler real-time* (eBPF, BCC, Sentry native, Linux `perf`) dapat mengekstrak jejak panggilan stack tanpa overhead resolusi DWARF.
- [ ] **Strict Bounded Recursion:** Setiap fungsi rekursif wajib menerima parameter *depth* eksplisit, contoh: `int parse(AST *node, size_t depth)` dan memutus alur jika `depth > RUNTIME_MAX_DEPTH`.

---

### 12. Hands-on Practice
Langkah-langkah praktikum berikut harus dijalankan dan file disimpan pada direktori: `hands-on/m02/`.

#### File Setup:
Buat struktur direktori:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

#### Langkah 1: Buat Implementation File (`hands-on/m02/trampoline_tco.c`)
File ini mendemonstrasikan transformasi rekursif mutual yang menyebabkan stack overflow menjadi implementasi berbasis *Trampoline Pattern* yang aman dan beroperasi pada stack space $O(1)$.

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>

// Deklarasi struktur Thunk (Deferred Computation)
struct Thunk;
typedef struct Thunk (*ThunkFn)(void *data);

typedef struct Thunk {
    ThunkFn fn;
    void *data;
    uint64_t result;
    bool is_final;
} Thunk;

// Payload state untuk perhitungan mutual even/odd
typedef struct {
    uint64_t n;
} NumberPayload;

// Forward declaration
Thunk is_odd(void *data);
Thunk is_even(void *data);

Thunk is_even(void *data) {
    NumberPayload *p = (NumberPayload *)data;
    if (p->n == 0) {
        return (Thunk){ .fn = NULL, .data = NULL, .result = 1, .is_final = true };
    }
    p->n -= 1;
    return (Thunk){ .fn = is_odd, .data = p, .result = 0, .is_final = false };
}

Thunk is_odd(void *data) {
    NumberPayload *p = (NumberPayload *)data;
    if (p->n == 0) {
        return (Thunk){ .fn = NULL, .data = NULL, .result = 0, .is_final = true };
    }
    p->n -= 1;
    return (Thunk){ .fn = is_even, .data = p, .result = 0, .is_final = false };
}

// Trampoline Engine: Menjalankan eksekusi tanpa pertambahan stack frame
uint64_t run_trampoline(Thunk initial) {
    Thunk current = initial;
    while (!current.is_final) {
        current = current.fn(current.data);
    }
    return current.result;
}

int main(int argc, char **argv) {
    uint64_t iterations = 50000000; // 50 Juta iterasi: Rekursi naif akan crash seketika
    if (argc > 1) {
        iterations = strtoull(argv[1], NULL, 10);
    }

    printf("Executing Trampoline Engine for N = %lu steps...\n", iterations);
    NumberPayload payload = { .n = iterations };
    Thunk initial = { .fn = is_even, .data = &payload, .result = 0, .is_final = false };

    uint64_t result = run_trampoline(initial);
    printf("Result: %lu is %s\n", iterations, result == 1 ? "EVEN" : "ODD");
    return 0;
}
```

#### Langkah 2: Buat Automated Makefile (`hands-on/m02/Makefile`)
```makefile
CC = gcc
CFLAGS = -Wall -Wextra -Werror -pedantic -std=c11 -O2 -fno-omit-frame-pointer -fstack-protector-strong
TARGET = trampoline_app

all: $(TARGET)

$(TARGET): trampoline_tco.c
	$(CC) $(CFLAGS) trampoline_tco.c -o $(TARGET)

disasm: $(TARGET)
	objdump -d -M intel $(TARGET) > trampoline_app.asm

run: $(TARGET)
	./$(TARGET) 50000000

clean:
	rm -f $(TARGET) trampoline_app.asm
```

#### Langkah 3: Eksekusi & Validasi
Jalankan di shell terminal:
```bash
make
make run
make disasm
```
Periksa file `trampoline_app.asm` untuk memverifikasi struktur epilogue, prologue, dan ketiadaan call instruction rekursif pada fungsi *trampoline loop*.

---

### 13. Exercise

#### Level Easy:
Tulis sebuah fungsi C `void print_stack_pointer_distance(void)` yang memanggil fungsi rekursif sedalam 3 tingkat. Setiap level harus mencetak alamat memori dari variabel lokalnya sendiri dan menghitung selisih jarak byte (`delta`) antar frame.
- **Kriteria Keberhasilan:** Terlihat konsistensi offset alokasi memori stack frame yang bergerak turun (alamat makin mengecil).

#### Level Medium:
Tulis fungsi assembly inline atau C dengan flag kompilasi GCC yang mengekstrak nilai *Return Address* dari fungsi pemanggil (*caller*) tanpa menggunakan header runtime compiler bawaan (dilarang menggunakan `__builtin_return_address`).
- **Kriteria Keberhasilan:** Menggunakan inline assembly atau pointer dereference dari `%rbp` (dengan asumsi `-fno-omit-frame-pointer`) untuk mengambil 8 byte yang berada di `8(%rbp)` dan mencetaknya dalam format pointer (`%p`), cocok dengan output address di map `nm` atau `gdb`.

#### Level Hard:
Konversikan algoritma QuickSort rekursif klasik menjadi implementasi iteratif murni yang menggunakan *Bounded Explicit Stack* berukuran tetap di stack memory (`StackEntry stack[64]`).
- **Kriteria Keberhasilan:**
  1. Mampu mengurutkan array sebesar 10.000.000 integer acak tanpa alokasi heap (`malloc`).
  2. Implementasi wajib menggunakan *tail recursion elimination* parsial (selalu push partisi yang lebih besar ke stack dan iterasi langsung partisi yang lebih kecil) untuk membuktikan batas kedalaman maksimum stack tidak akan melebihi $\log_2(N) \approx 24$ slot.

---

### 14. Challenge

**Skenario Sistem:**  
Anda ditugaskan merancang *Coroutines Context Switcher* manual murni arsitektur x86_64 untuk subsistem antrean pesan (*message broker*) dengan kriteria zero runtime overhead (tanpa libc `ucontext`, tanpa POSIX signal masks).

**Persyaratan Arsitektur:**
1. Tulis fungsi assembly independen `void context_switch(uintptr_t **old_sp, uintptr_t *new_sp);` dalam berkas assembly `.S`.
2. Fungsi wajib menyimpan seluruh register *callee-saved* milik System V AMD64 (`%rbx`, `%rsp`, `%rbp`, `%r12`, `%r13`, `%r14`, `%r15`) ke stack thread lama.
3. Fungsi menukar penunjuk stack: menyimpan `%rsp` saat ini ke `*old_sp` dan memuat `new_sp` ke dalam register `%rsp`.
4. Fungsi memulihkan seluruh register *callee-saved* dari stack baru dan mengeksekusi instruksi `ret` untuk melanjutkan eksekusi di titik thread baru.
5. Tangani skenario bootstrap: Saat fiber pertama kali dieksekusi, fiber harus memulai fungsinya dengan stack yang selaras 16-byte dan memiliki rute pembersihan jika fungsi thread me-return nilainya.

**Deliverables:**
- File `switch.S` (Assembly System V murni).
- File `main_broker.c` (Engine driver menguji alur context switch antara dua coroutine minimal 10.000.000 kali per detik).

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. **Mengapa nilai `%rsp` pada arsitektur System V x86_64 wajib 16-byte aligned sebelum instruksi pemanggilan `call`?**
   - *Jawaban:* Karena spesifikasi ABI menetapkan alignment 16-byte guna menjamin instruksi SIMD/vectorized (seperti SSE/AVX yang memproses instruksi transfer memori aligned, contoh: `movaps`) tidak memicu kegagalan hardware exception (*General Protection Fault*).

2. **Apa yang dilakukan oleh instruksi CPU `call` dan `ret` pada tingkat hardware register?**
   - *Jawaban:* Instruksi `call` secara atomik mendorong (*push*) isi register `%rip` (Return Address / alamat instruksi selanjutnya) ke posisi `-8(%rsp)` dan mengurangi nilai `%rsp` sebesar 8, lalu melompat ke alamat target. Instruksi `ret` mengambil (*pop*) nilai 8-byte dari alamat yang ditunjuk `%rsp`, memasukkannya kembali ke register `%rip`, dan menambah `%rsp` sebesar 8.

3. **Apa kegunaan utama dari register `%rbp` dalam konvensi pemanggilan standar?**
   - *Jawaban:* Sebagai *Base Pointer* atau *Frame Pointer* yang menyediakan jangkar alamat statis tetap untuk mereferensikan variabel lokal dan argumen di dalam frame fungsi tertentu, independen terhadap perubahan `%rsp` selama operasi `push`/`pop` dinamis.

4. **Apa yang dimaksud dengan "Red Zone" pada System V AMD64 ABI?**
   - *Jawaban:* Area memori selebar 128 byte di bawah `%rsp` yang dialokasikan dan dijamin aman dari interupsi OS bagi fungsi leaf, sehingga fungsi leaf dapat menyimpan data lokal sementara tanpa perlu memodifikasi stack pointer `%rsp`.

5. **Apa efek negatif dari penggunaan alokasi array C99 VLA (`int arr[n];`) di dalam fungsi?**
   - *Jawaban:* VLA memodifikasi `%rsp` secara dinamis pada saat runtime tanpa jaminan pemeriksaan batas stack. Jika nilai `n` terlalu besar, stack seketika melompati guard page OS yang mengakibatkan crash tak terkendali (*stack overflow/stack clash*).

#### 5 Pertanyaan Intermediate
6. **Kapan compiler TIDAK BISA menerapkan Tail Call Optimization (TCO) meskipun fungsi rekursif ditulis pada baris return?**
   - *Jawaban:* Ketika fungsi caller harus melakukan operasi evaluasi, komputasi, pembersihan variabel lokal yang memiliki destructors/cleanup attributes, atau ketika caller perlu mengakses alamat memori variabel lokalnya sendiri setelah pemanggilan fungsi anak.

7. **Bagaimana mekanisme proteksi Stack Canary (`-fstack-protector-strong`) membedakan fungsi yang perlu diproteksi versus yang tidak?**
   - *Jawaban:* Standar `-fstack-protector-strong` menyisipkan canary hanya jika fungsi mengalokasikan buffer array berukuran berapa pun pada stack, memanggil `alloca()`, atau mengambil alamat referensi dari variabel lokalnya sendiri.

8. **Apa perbedaan dampak profiler antara binary yang dikompilasi dengan `-fomit-frame-pointer` versus `-fno-omit-frame-pointer`?**
   - *Jawaban:* Binary dengan `-fomit-frame-pointer` membebaskan satu register serbaguna (`%rbp`) untuk meningkatkan performa komputasi, namun profiler eBPF/perf berkecepatan tinggi tidak dapat melakukan unwinding call graph secara instan dan harus mengandalkan DWARF call frame information (`.eh_frame`) yang membebani resource parsing.

9. **Sebutkan urutan register System V AMD64 untuk melewatkan 6 argumen pertama bertipe integer atau pointer!**
   - *Jawaban:* `%rdi` (argumen 1), `%rsi` (argumen 2), `%rdx` (argumen 3), `%rcx` (argumen 4), `%r8` (argumen 5), dan `%r9` (argumen 6).

10. **Bagaimana fungsi `longjmp` memulihkan alur program yang sebelumnya ditandai oleh `setjmp`?**
    - *Jawaban:* `longjmp` menyalin nilai-nilai register penting yang disimpan di dalam struktur data `jmp_buf` (seperti `%rsp`, `%rbp`, dan `%rip`) kembali ke CPU hardware register, sehingga mengembalikan kondisi eksekusi langsung ke titik pemanggilan `setjmp` dengan nilai kembalian non-nol.

#### 3 Skenario Kasus Produksi
11. **Skenario A:** Server microservice payment gateway berbasis C sering mengalami crash acak *Segmentation Fault* hanya saat volume traffic tinggi, tetapi coredump selalu menunjukkan bahwa crash terjadi di tengah instruksi SIMD `movaps %xmm0, (%rsp)`. Di manakah akar masalahnya?
    - *Analisis Solusi:* Terjadi pelanggaran *16-byte stack alignment*. Ada fungsi perantara (biasanya fungsi wrapper hand-written assembly atau callback pihak ketiga) yang memodifikasi stack tanpa menjaga kelipatan 16 byte sebelum pemanggilan fungsi libc/SIMD, sehingga saat instruksi `movaps` dieksekusi dengan alamat yang tidak habis dibagi 16, CPU membangkitkan exception hardware GPF.

12. **Skenario B:** Tim security menemukan kerentanan buffer overflow pada protokol legacy C, namun binary telah dikompilasi dengan flag proteksi canary. Bagaimana eksploitasi format string attack tetap dapat membaca canary tersebut?
    - *Analisis Solusi:* Format string attack (misalnya melalui format penentu `%lx` yang tidak divalidasi pada `printf(user_input)`) membaca data dari stack frame pemanggil secara sekuensial. Penyerang dapat membocorkan (*leak*) nilai canary yang tersimpan di stack, menyimpannya di payload jaringan, lalu menimpa stack dengan menyertakan nilai canary asli yang tepat sehingga cek validasi `__stack_chk_fail` dilewati dengan sukses.

13. **Skenario C:** Profiling kernel menggunakan eBPF pada aplikasi database throughput tinggi menunjukkan overhead CPU profiling naik hingga 35% saat parsing stack traces. Setelah diselidiki, opsi kompilasi menggunakan `-fomit-frame-pointer`. Bagaimana solusinya?
    - *Analisis Solusi:* Kompilasi ulang binary produksi dengan `-fno-omit-frame-pointer`. Hal ini menjaga `%rbp` tetap teratur sebagai penunjuk frame tautan berantai (*linked list of frames*), sehingga agent eBPF di ring 0 dapat melakukan traversal stack trace hanya dalam hitungan puluhan nanodetik via pembacaan register tanpa harus menghentikan thread atau mengurai binary debug format DWARF yang berat.

---

### 16. Summary
1. **Integritas Stack Frame:** Setiap pemanggilan fungsi di arsitektur modern x86_64 diatur ketat oleh ABI, yang mengendalikan alokasi memori, pelestarian register (*caller-saved* vs *callee-saved*), serta restriksi *16-byte alignment*.
2. **Mitigasi Keamanan & Stabilitas:** Stack canary (`-fstack-protector-strong`) dan penghapusan dynamic allocation VLA/`alloca` adalah fondasi mutlak sistem enterprise untuk mencegah eksploitasi kontrol alur dan insiden *stack exhaustion*.
3. **Optimasi Rekursi vs Produksi:** Rekursi tanpa pembatas kedalaman adalah anti-pattern dalam perangkat lunak enterprise. Kompiler dapat mengoptimasi rekursi murni via Tail Call Optimization (TCO), sedangkan algoritma traversal kompleks harus beralih ke struktur *Explicit Heap Stack* atau *Trampoline Architecture*.
4. **Manipulasi Konteks Eksekusi:** Pemanfaatan `setjmp`/`longjmp` dan modifikasi register penunjuk stack memungkinkan implementasi komponen performa tinggi seperti fibers/coroutines di ruang pengguna (*userspace*) tanpa overhead context switching kernel thread.