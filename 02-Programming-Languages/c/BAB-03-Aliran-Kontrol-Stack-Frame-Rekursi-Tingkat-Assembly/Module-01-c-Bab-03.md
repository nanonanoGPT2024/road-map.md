# ALIRAN KONTROL, STACK FRAME, & REKURSI TINGKAT ASSEMBLY

---

## SEKSI 01 — IDENTITAS MODUL

*   **Modul:** Bab 03 Module 01 — Aliran Kontrol, Stack Frame, & Rekursi Tingkat Assembly
*   **Kategori:** 02-Programming-Languages
*   **Track:** C (Systems Programming & Low-Level Architecture)
*   **Target Audiens:** Systems Software Engineer, Firmware/Kernel Developer, Security Researcher, Compiler Enthusiast.
*   **Prasyarat:** Pemahaman fundamental sintaksis C, pointer dereferencing, representasi data biner/heksadesimal, dan model memori virtual sederhana (Stack, Heap, Data, Text).
*   **Arsitektur Target:** x86_64 (AMD64) System V ABI (Linux standard).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara komprehensif, pembaca diharapkan mampu:

1.  **Mendekonstruksi** instruksi C tingkat tinggi (`if-else`, loop, pemanggilan fungsi, rekursi) menjadi representasi instruksi assembly x86_64 (`cmp`, `test`, `jmp`, `jcc`, `call`, `ret`).
2.  **Membedah Anatomi Stack Frame** secara eksak pada tingkat bita dan register, memetakan interaksi antara Stack Pointer (`%rsp`), Base/Frame Pointer (`%rbp`), Program Counter/Instruction Pointer (`%rip`), serta konvensi register ABI.
3.  **Menganalisis Mekanisme Rekursi** pada lapisan mikroskopis memori, termasuk dinamika penambahan stack frame, batas pertumbuhan stack (stack limit/red zone), dan pemanfaatan Tail-Call Optimization (TCO).
4.  **Mengidentifikasi dan Mencegah Kerentanan** terkait stack, seperti *Stack Overflow*, *Stack-Smashing*, dan korupsi frame pointer melalui pendekatan rekayasa perangkat lunak defensif.
5.  **Melakukan Debugging Tingkat Mesin** menggunakan GNU Debugger (`gdb`) dengan membaca raw stack memory, menginspeksi register prosesor, serta merekonstruksi call stack secara manual.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Ilusi Abstraksi Bahasa C

Bahasa C sering kali dijuluki sebagai *"high-level assembly"*, namun ia tetap menyembunyikan realitas mesin fisik. Di tingkat C, fungsi tampak seperti kotak hitam yang menerima parameter independen, menciptakan variabel lokal dari ketiadaan, dan mengembalikan sebuah nilai.

```
Model Mental C:
[main()] --- argumen ---> [faktorial(5)] --- return val ---> [main()]
```

### Realitas Fisik Perangkat Keras

Pada level sirkuit mikroarsitektur, konsep "fungsi" **tidak ada**. Mesin hanya mengenali:
1.  **Register:** Kompartemen penyimpanan data super-cepat yang berada langsung di dalam CPU (ordo pikosekon).
2.  **Instruction Pointer (`%rip`):** Penunjuk alamat memori dari instruksi berikutnya yang harus diambil (*fetched*), didekode (*decoded*), dan dieksekusi (*executed*).
3.  **Linear Memory (RAM/Cache):** Ruang alamat logis array 1 dimensi dari bita-bita tanpa tipe data.

Pemanggilan fungsi sebenarnya hanyalah kombinasi manipulasi alur eksekusi (mengubah nilai register `%rip`) dan perjanjian (*calling convention*) tentang lokasi penyimpanan konteks sebelum eksekusi berpindah. Stack hanyalah wilayah konvensional dari RAM yang dikelola melalui dua register khusus (`%rsp` dan `%rbp`) yang tumbuh ke arah alamat memori yang lebih rendah (*downward growth*). 

Rekursi bukanlah fenomena abstrak matematis, melainkan instruksi percabangan bersyarat (*conditional branch*) yang memicu replikasi alokasi memori beruntun di stack hingga sebuah predikat terminasi menghentikan alokasi dan memicu instruksi pemulihan frame (*epilogue*) secara berantai.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram 1: Evolusi Stack Frame x86_64 (System V ABI)

Ketika fungsi pemanggil (*Caller*) memanggil fungsi target (*Callee*), layout memori stack berkembang ke bawah (*downward towards lower addresses*).

```
Tinggi Alamat Memori (0x7FFFFFFFFFFF)
+-------------------------------------------------------+
|                 Caller's Stack Frame                  |
|  ...                                                  |
|  Argumen ke-7, ke-8 (jika ada, dipush terbalik)       |
+-------------------------------------------------------+
|  Return Address (%rip yang disimpan oleh `call`)      | <- %rsp sebelum `push %rbp`
+-------------------------------------------------------+ <- %rbp (setelah `mov %rsp, %rbp`)
|  Saved Frame Pointer (Old %rbp milik Caller)          |
+-------------------------------------------------------+
|  Variabel Lokal & Array Callee                        |
|  (misal: int buffer[64])                              |
|  ... dialokasikan via `sub $N, %rsp`                  |
+-------------------------------------------------------+
|  Callee-Saved Registers (%rbx, %r12, %r13, %r14, %r15)|
+-------------------------------------------------------+ <- %rsp (Stack Pointer saat ini)
|  RED ZONE (128 bytes) - Khusus Leaf Function          |
|  (Hanya berlaku di System V AMD64 ABI, tidak boleh    |
|   diinterupsi oleh asynchronous signal handlers)      |
+-------------------------------------------------------+
Rendah Alamat Memori (0x000000000000)
```

### Diagram 2: Alur Siklus Hidup Eksekusi Pemanggilan Fungsi

```
  CALLER                                      CALLEE
+-----------------------------------+       +------------------------------------+
| 1. Simpan Caller-saved registers  |       |                                    |
| 2. Muat Argumen 1-6 ke register:  |       |                                    |
|    %rdi, %rsi, %rdx, %rcx, %r8, %r9|       |                                    |
| 3. Push argumen sisa (jika > 6)   |       |                                    |
| 4. Jalankan instruksi `call`:     | ===>  | 5. Function Prologue:              |
|    - Push (%rip + offset)         |       |    push %rbp                       |
|    - Jmp ke label Callee          |       |    mov %rsp, %rbp                  |
|                                   |       |    sub $space, %rsp                |
|                                   |       | 6. Eksekusi logika Callee          |
|                                   |       | 7. Tempatkan return value di %rax  |
|                                   |  <=== | 8. Function Epilogue:              |
|                                   |       |    mov %rbp, %rsp (atau `leave`)   |
|                                   |       |    pop %rbp                        |
| 9. Lanjutkan eksekusi dari %rip   |       |    ret (pop %rip dan jmp)          |
|10. Bersihkan argumen stack        |       +------------------------------------+
+-----------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Register Set x86_64 dan Aturan System V ABI

Arsitektur x86_64 menyediakan enam belas register serbaguna (*general-purpose registers*) berukuran 64-bit. System V AMD64 ABI menetapkan peranan mutlak untuk masing-masing register:

| Register | Peranan dalam Calling Convention | Preservasi (*Owner*) |
| :--- | :--- | :--- |
| `%rax` | Nilai balik pertama fungsi (*Return Value*) | Caller-saved (*Scratch*) |
| `%rdx` | Nilai balik kedua fungsi / Argumen ke-3 | Caller-saved |
| `%rdi` | Argumen ke-1 | Caller-saved |
| `%rsi` | Argumen ke-2 | Caller-saved |
| `%rdx` | Argumen ke-3 | Caller-saved |
| `%rcx` | Argumen ke-4 | Caller-saved |
| `%r8`  | Argumen ke-5 | Caller-saved |
| `%r9`  | Argumen ke-6 | Caller-saved |
| `%rsp` | Stack Pointer (menunjuk ke posisi teratas stack) | Callee-saved |
| `%rbp` | Frame Pointer / Base Pointer | Callee-saved |
| `%rbx` | Variabel lokal / General purpose | Callee-saved |
| `%r12` - `%r15` | Variabel lokal / General purpose | Callee-saved |
| `%r10` - `%r11` | Register temporer | Caller-saved |
| `%rip` | Instruction Pointer (tidak dapat dimodifikasi langsung via `mov`)| Dikelola otomatis |

*   **Caller-saved (`scratch`):** Jika *caller* ingin nilainya bertahan setelah memanggil fungsi lain, *caller* harus menyimpannya ke stack sebelum instruksi `call`.
*   **Callee-saved:** Fungsi yang dipanggil (*callee*) wajib mengembalikan nilai register ini ke kondisi semula sebelum kembali (`ret`).

### 2. Aturan Stack Alignment 16-Byte

System V ABI mensyaratkan bahwa stack pointer (`%rsp`) harus memiliki **alignment 16-byte** tepat sebelum instruksi `call` dieksekusi. Artinya:
$$\%rsp \pmod{16} == 0$$
Ketika instruksi `call` dipanggil, CPU secara otomatis mem-*push* Return Address (8 byte) ke stack. Akibatnya, pada saat fungsi Callee dimasuki, alignment stack berubah menjadi:
$$\%rsp \pmod{16} == 8$$
Oleh karena itu, dalam fungsi *prologue*, Callee sering melakukan manipulasi alignment (seperti `push %rbp` yang menambahkan 8 byte lagi, mengembalikan alignment menjadi kelipatan 16) sebelum mengalokasikan ruang lokal melalui instruksi pengurangan `%rsp`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Percabangan Bersyarat (*Conditional Branching*) dan Condition Codes

Bahasa C menyembunyikan status flags prosesor. CPU x86_64 menggunakan register khusus bernama `RFLAGS` yang menampung bit-bit status:
*   `ZF` (Zero Flag): Aktif jika hasil operasi aritmatika/logika bernilai nol.
*   `SF` (Sign Flag): Aktif jika bit paling signifikan bernilai 1 (hasil negatif).
*   `OF` (Overflow Flag): Aktif jika terjadi overflow komplemen-dua bertanda.
*   `CF` (Carry Flag): Aktif jika terjadi carry/borrow operasi tak bertanda.

Instruksi `cmp a, b` bekerja dengan cara mengkalkulasi selisih `b - a` tanpa menyimpan hasilnya ke register destinasi, melainkan hanya memodifikasi `RFLAGS`. Instruksi percabangan (`jcc`) bertindak langsung berdasarkan flags tersebut:
*   `je` / `jz` (*Jump if Equal / Zero*): Lompat jika `ZF == 1`.
*   `jne` / `jnz` (*Jump if Not Equal / Not Zero*): Lompat jika `ZF == 0`.
*   `jl` / `jnge` (*Jump if Less*): Lompat jika `SF != OF` (aritmatika bertanda).
*   `jle` (*Jump if Less or Equal*): Lompat jika `(SF != OF) || (ZF == 1)`.

### 2. Mekanisme Rekursi Tingkat Mesin

Rekursi terjadi ketika sebuah fungsi memanggil dirinya sendiri. Secara fisik:
1. Setiap iterasi rekursif adalah **pemanggilan fungsi independen baru**.
2. Setiap langkah rekursif mengeksekusi instruksi `call`, yang:
   * Mengurangi `%rsp` sebanyak 8 byte.
   * Menuliskan alamat instruksi lanjutan (`%rip`) ke dalam alamat memori `[%rsp]`.
   * Mengalokasikan blok baru untuk frame Callee.
3. Kedalaman rekursi linier $N$ mengonsumsi $O(N)$ ruang stack secara kontinu.

### 3. Tail-Call Optimization (TCO)

Tail Call adalah situasi di mana panggilan fungsi terakhir yang dieksekusi Callee adalah pemanggilan fungsi lain (atau dirinya sendiri), dan nilainya langsung dikembalikan tanpa operasi tambahan:

```c
// Bukan Tail Recursion (memerlukan perkalian setelah panggilan kembali)
uint64_t fact_normal(uint64_t n) {
    if (n <= 1) return 1;
    return n * fact_normal(n - 1); 
}

// Tail Recursion (nilai balik fungsi langsung dikembalikan secara mutlak)
uint64_t fact_tail(uint64_t n, uint64_t acc) {
    if (n <= 1) return acc;
    return fact_tail(n - 1, n * acc);
}
```

Pada level assembly dengan optimasi (`-O2` / `-O3`), compiler cerdas tidak memancarkan instruksi `call` berulang kali. Alih-alih membuat frame stack baru, compiler hanya memperbarui argumen di register (`%rdi`, `%rsi`) dan mengeksekusi instruksi `jmp` kembali ke awal fungsi yang sama. Rekursi diubah secara fisik menjadi **looping instruksi tunggal**, mengurangi kompleksitas ruang memori dari $O(N)$ menjadi $O(1)$.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi fungsi rekursi linear dan tail-recursive untuk menghitung nilai Fibonacci, yang siap dikompilasi dan dibedah pada tingkatan assembly.

```c
/**
 * @file control_stack.c
 * @brief Implementasi demonstrasi Stack Frame dan Analisis Rekursi
 */

#include <stdio.h>
#include <stdint.h>

// 1. Rekursi Linear Standar (Membuat Frame Baru di Setiap Panggilan)
uint64_t fibonacci_standard(uint64_t n) {
    if (n == 0) return 0;
    if (n == 1) return 1;
    return fibonacci_standard(n - 1) + fibonacci_standard(n - 2);
}

// 2. Rekursi Tail-Call (Kandidat untuk Optimasi Compiler Menjadi Loop)
uint64_t fibonacci_tail_rec(uint64_t n, uint64_t a, uint64_t b) {
    if (n == 0) return a;
    if (n == 1) return b;
    return fibonacci_tail_rec(n - 1, b, a + b);
}

int main(void) {
    uint64_t target = 10;
    
    uint64_t res1 = fibonacci_standard(target);
    uint64_t res2 = fibonacci_tail_rec(target, 0, 1);

    printf("Fibonacci Standard (%lu): %lu\n", target, res1);
    printf("Fibonacci Tail-Rec (%lu): %lu\n", target, res2);

    return 0;
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mari kita bedah keluaran assembly x86_64 dari fungsi `fibonacci_tail_rec` dengan dua konfigurasi compiler: tanpa optimasi (`-O0`) dan dengan optimasi (`-O2`).

### 1. Disassembly Tanpa Optimasi (`gcc -O0 -fno-omit-frame-pointer`)

```assembly
fibonacci_tail_rec:
    # --- PROLOGUE ---
    pushq   %rbp                 # 1. Simpan frame pointer caller ke stack
    movq    %rsp, %rbp           # 2. Set frame pointer Callee ke stack pointer saat ini
    subq    $32, %rsp            # 3. Alokasikan 32-byte memori stack untuk variabel lokal/parameter
    movq    %rdi, -8(%rbp)       # 4. Simpan n (%rdi) ke stack local
    movq    %rsi, -16(%rbp)      # 5. Simpan a (%rsi) ke stack local
    movq    %rdx, -24(%rbp)      # 6. Simpan b (%rdx) ke stack local

    # --- BASE CASE 1: if (n == 0) return a; ---
    cmpq    $0, -8(%rbp)         # 7. Bandingkan n dengan 0
    jne     .L_CHECK_ONE         # 8. Jika n != 0, lompat ke pengecekan berikutnya
    movq    -16(%rbp), %rax      # 9. Return a (pindahkan 'a' ke register %rax)
    jmp     .L_EPILOGUE          # 10. Lompat ke epilogue

.L_CHECK_ONE:
    # --- BASE CASE 2: if (n == 1) return b; ---
    cmpq    $1, -8(%rbp)         # 11. Bandingkan n dengan 1
    jne     .L_RECURSE           # 12. Jika n != 1, lompat ke pemanggilan rekursif
    movq    -24(%rbp), %rax      # 13. Return b (pindahkan 'b' ke register %rax)
    jmp     .L_EPILOGUE

.L_RECURSE:
    # --- RECURSIVE CALL: fibonacci_tail_rec(n - 1, b, a + b) ---
    movq    -8(%rbp), %rax       # 14. Muat n ke %rax
    leaq    -1(%rax), %rdi       # 15. Hitung n - 1, tempatkan pada Arg 1 (%rdi)
    movq    -16(%rbp), %rax      # 16. Muat a ke %rax
    movq    -24(%rbp), %rdx      # 17. Muat b ke %rdx
    addq    %rax, %rdx           # 18. Hitung a + b, simpan pada Arg 3 (%rdx)
    movq    -24(%rbp), %rsi      # 19. Muat b ke Arg 2 (%rsi)
    call    fibonacci_tail_rec   # 20. Eksekusi rekursif (PUSH %rip dan JMP)

.L_EPILOGUE:
    # --- EPILOGUE ---
    leave                        # 21. Sederajat dengan: mov %rbp, %rsp; pop %rbp
    ret                          # 22. Ambil return address dari stack dan lompat
```

*   **Baris 1-3:** *Standard Function Prologue*. Alamat frame lama dipertahankan, dan ruang stack dialokasikan.
*   **Baris 4-6:** Register ABI disalin ke ruang stack lokal karena compiler `-O0` tidak mempertahankan variabel di register.
*   **Baris 20:** Instruksi `call` mendorong return address ke stack dan melompat. Ini mengonsumsi 40 byte total per frame (`push %rbp` [8 byte] + `subq $32, %rsp` [32 byte]).
*   **Baris 21-22:** *Epilogue*. Instruksi `leave` merestorasi stack frame Caller, lalu `ret` mengambil alamat lanjutan Caller dari stack ke `%rip`.

---

### 2. Disassembly Dengan Optimasi (`gcc -O2`)

```assembly
fibonacci_tail_rec:
.LFB1:
    testq   %rdi, %rdi           # 1. Tes apakah n == 0 (lebih cepat dari cmpq $0)
    je      .L4                  # 2. Jika 0, lompat ke penanganan exit dengan %rax = a
    cmpq    $1, %rdi             # 3. Tes apakah n == 1
    je      .L8                  # 4. Jika 1, lompat ke penanganan exit dengan %rax = b

.L3:
    # --- TAIL-CALL LOOP (TCO DIAPLIKASIKAN) ---
    leaq    (%rsi,%rdx), %rax    # 5. %rax = a + b
    decq    %rdi                 # 6. n = n - 1
    movq    %rdx, %rsi           # 7. a = b
    movq    %rax, %rdx           # 8. b = a + b
    cmpq    $1, %rdi             # 9. Apakah n == 1?
    jne     .L3                  # 10. Jika n != 1, lompat ke loop (.L3) TANPA MEMBUAT STACK BARU

.L8:
    movq    %rdx, %rax           # 11. Muat b ke register return %rax
    ret                          # 12. Kembali ke caller utama

.L4:
    movq    %rsi, %rax           # 13. Muat a ke register return %rax
    ret
```

*   **Peniadaan Prologue/Epilogue:** Fungsi ini tidak lagi memanipulasi `%rsp` atau menyimpan `%rbp` (disebut *Leaf Function* teroptimasi).
*   **Baris 10:** Tidak ada instruksi `call`. Pemanggilan fungsi telah direduksi menjadi `jne .L3` (lompatan internal). Konsumsi memori stack ditekan dari $O(N)$ menjadi mutlak $0$ byte tambahan!

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Permasalahan: Stack Overflow pada JSON Recursive Descent Parser

Dalam sebuah sistem microservice pemrosesan telemetri IoT berperforma tinggi, layanan menerima payload JSON bersarang (*deeply nested arrays/objects*). Parser yang digunakan ditulis dalam C menggunakan teknik *Recursive Descent Parsing*.

```json
{"a": {"a": {"a": {"a": ... (bersarang hingga kedalaman 50.000 tingkat) ... }}}}
```

Ukuran default Linux pthread stack adalah **8 Megabytes** (atau hanya **512 Kilobytes - 2 Megabytes** pada lingkungan embedded/musl libc). 
Setiap kali fungsi `parse_json_value()` memanggil fungsi parsing rekursif:
1. Frame stack mengonsumsi memori sebesar 256 byte (alokasi buffer token, context pointer, alignment padding).
2. Kedalaman 50.000 nesting membutuhkan:
   $$50.000 \times 256\text{ byte} = 12.800.000\text{ byte} \approx 12,2\text{ MB}$$
3. Memori melampaui alokasi stack maksimum. Stack Pointer (`%rsp`) menabrak *Guard Page* (halaman virtual memory tanpa izin read/write yang dipasang OS di ujung stack).
4. CPU melempar *Hardware Page Fault Interrupt*. Kernel menangkap pelanggaran ini dan mengirimkan sinyal `SIGSEGV` (*Segmentation Fault*). Layanan mati (*crash*) seketika—memicu serangan **Denial-of-Service (DoS)**.

### Solusi Teknis
Mengganti mekanisme rekursi implisit hardware (stack call) dengan **Manual Explicit Stack** yang dialokasikan di atas Virtual Memory Heap, atau mengubah algoritma traversal menjadi model iteratif berbasis status (*State Machine Trampoline*).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi parser struktur pohon bersarang yang tahan banting (*production-grade*). Program mendemonstrasikan bagaimana rekursi naif memicu malapetaka dan bagaimana mengimplementasikan **Explicit Heap Stack Traversal** dengan batasan kedalaman terkontrol (*depth-limiting guard*).

```c
/**
 * @file safe_depth_traversal.c
 * @brief Traversal Pohon Data Bersarang Ekstrem: Rekursi Naif vs Explicit Heap Stack
 * Kompilasi: gcc -Wall -Wextra -O2 safe_depth_traversal.c -o safe_traversal
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>

#define MAX_SAFE_DEPTH 1000000 // 1 Juta Kedalaman
#define STACK_CAPACITY 65536

typedef struct TreeNode {
    int64_t value;
    struct TreeNode *next_child;
} TreeNode;

// -------------------------------------------------------------
// METODE 1: Rekursif Naif (Rentan Stack Overflow)
// -------------------------------------------------------------
int64_t sum_tree_recursive(const TreeNode *root, size_t *current_depth) {
    if (root == NULL) return 0;
    
    (*current_depth)++;
    // PERINGATAN: Pada sistem produksi, penumpukan frame di sini akan memicu SIGSEGV
    int64_t sub_total = sum_tree_recursive(root->next_child, current_depth);
    return root->value + sub_total;
}

// -------------------------------------------------------------
// METODE 2: Explicit Heap Stack (Aman dari Keterbatasan Ukuran Thread Stack)
// -------------------------------------------------------------
typedef struct {
    const TreeNode **nodes;
    size_t top;
    size_t capacity;
} ExplicitStack;

static ExplicitStack* create_stack(size_t capacity) {
    ExplicitStack *stack = (ExplicitStack *)malloc(sizeof(ExplicitStack));
    if (!stack) return NULL;
    
    stack->nodes = (const TreeNode **)malloc(capacity * sizeof(TreeNode *));
    if (!stack->nodes) {
        free(stack);
        return NULL;
    }
    stack->top = 0;
    stack->capacity = capacity;
    return stack;
}

static void free_stack(ExplicitStack *stack) {
    if (stack) {
        free(stack->nodes);
        free(stack);
    }
}

static bool push_stack(ExplicitStack *stack, const TreeNode *node) {
    if (stack->top >= stack->capacity) {
        // Dinamis menggandakan kapasitas jika stack manual meluap
        size_t new_cap = stack->capacity * 2;
        const TreeNode **new_nodes = (const TreeNode **)realloc(stack->nodes, new_cap * sizeof(TreeNode *));
        if (!new_nodes) return false;
        
        stack->nodes = new_nodes;
        stack->capacity = new_cap;
    }
    stack->nodes[stack->top++] = node;
    return true;
}

static const TreeNode* pop_stack(ExplicitStack *stack) {
    if (stack->top == 0) return NULL;
    return stack->nodes[--stack->top];
}

// Traversal Iteratif Bebas Risiko Stack Frame Overflow
bool sum_tree_iterative(const TreeNode *root, int64_t *out_sum) {
    if (!root || !out_sum) return false;

    ExplicitStack *stack = create_stack(1024);
    if (!stack) return false;

    int64_t total = 0;
    const TreeNode *curr = root;

    while (curr != NULL || stack->top > 0) {
        while (curr != NULL) {
            if (!push_stack(stack, curr)) {
                free_stack(stack);
                return false; // Alokasi heap gagal
            }
            curr = curr->next_child;
        }

        curr = pop_stack(stack);
        total += curr->value;
        curr = NULL; // Telusuri node berikutnya
    }

    *out_sum = total;
    free_stack(stack);
    return true;
}

// -------------------------------------------------------------
// DRIVER TEST
// -------------------------------------------------------------
int main(void) {
    // Alokasikan deep chain node secara linier di Heap
    const size_t test_depth = 50000; // Cukup untuk menguji ketahanan
    printf("[*] Membangun Linked-Chain sepanjang %zu node...\n", test_depth);
    
    TreeNode *head = (TreeNode *)malloc(sizeof(TreeNode));
    head->value = 1;
    head->next_child = NULL;

    TreeNode *curr = head;
    for (size_t i = 1; i < test_depth; ++i) {
        TreeNode *node = (TreeNode *)malloc(sizeof(TreeNode));
        node->value = 1;
        node->next_child = NULL;
        curr->next_child = node;
        curr = node;
    }

    printf("[+] Konstruksi selesai.\n");

    // Uji Pendekatan Rekursif Aman
    size_t depth_counter = 0;
    printf("[*] Menjalankan Traversal Iteratif (Explicit Heap Stack)...\n");
    int64_t sum_iter = 0;
    if (sum_tree_iterative(head, &sum_iter)) {
        printf("[SUCCESS] Total Perhitungan Iteratif: %ld\n", (long)sum_iter);
    } else {
        printf("[ERROR] Iterative Traversal Gagal.\n");
    }

    // Uji Coba Rekursif Naif (Awas Stack Overflow jika test_depth > batasan stack OS)
    printf("[*] Menjalankan Traversal Rekursif Naif (Depth Monitor)...\n");
    int64_t sum_rec = sum_tree_recursive(head, &depth_counter);
    printf("[SUCCESS] Total Perhitungan Rekursif: %ld (Mencapai Depth: %zu)\n", (long)sum_rec, depth_counter);

    // Dealokasi Memori
    curr = head;
    while (curr != NULL) {
        TreeNode *temp = curr->next_child;
        free(curr);
        curr = temp;
    }
    
    return 0;
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter | Rekursi Naif | Rekursi Tail-Call (TCO Diaktifkan) | Iterasi Murni | Explicit Heap Stack |
| :--- | :--- | :--- | :--- | :--- |
| **Konsumsi Ruang Stack** | $O(N)$ (Sangat Tinggi) | $O(1)$ (Konstan) | $O(1)$ (Konstan) | $O(1)$ Stack Kernel/OS |
| **Konsumsi Memori Heap**| $0$ | $0$ | $0$ | $O(N)$ (Di Heap) |
| **Overhead Instruksi CPU**| Tinggi (`call`, `push`, `leave`, `ret`) | Minimal (`jmp`, register moves) | Minimal (`jmp`, instruksi perulangan) | Sedang (Manajemen struct & pointer manual) |
| **Batas Kedalaman Alami**| Terbatas ($\approx$ 8MB / Frame Size) | Dibatasi rentang tipe data register | Dibatasi rentang tipe data register | Dibatasi kapasitas total RAM (Gigabytes) |
| **Jaminan Optimasi** | Tidak ada | Bergantung Compiler (`-O2`, flags ABI) | Dijamin secara sintaksis | Dijamin secara algoritmik |
| **Keterbacaan Kode** | Sangat elegan, deklaratif | Bersih, sedikit boilerplate | Sedang | Rendah (Banyak boilerplate alokasi) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Red Zone Hazard (x86_64 ABI)
System V ABI mengalokasikan area 128-byte di bawah pointer `%rsp` yang disebut **Red Zone**. Fungsi *leaf* (yang tidak memanggil fungsi lain sama sekali) dapat menggunakan ruang ini untuk data temporer tanpa perlu menyesuaikan `%rsp` via `subq`.

```assembly
# Leaf function aman menulis ke Red Zone
movq    %rdi, -8(%rsp)      # Alamat ini valid di Red Zone
ret
```

*Pitfall:* Jika kode bare-metal atau sistem operasi yang mengizinkan interrupt menangani interupsi hardware tanpa memindahkan stack pointer, penangan sinyal (*kernel interrupt handler*) dapat menimpa data pada Red Zone tersebut seketika. Pada kompilasi kernel Linux, flag `-mno-red-zone` **wajib** digunakan!

### 2. Variable Length Arrays (VLA) Merusak Alignment Stack
Penggunaan fitur VLA di C99:
```c
void process_packet(size_t len) {
    char dynamic_buffer[len]; // Mengalokasikan via manipulasi langsung ke %rsp
    // ...
}
```
Assembly yang dihasilkan akan mengeksekusi instruksi dinamis seperti `subq %rax, %rsp` dan operasi masking `andq $-16, %rsp` untuk mempertahankan alignment 16-byte. Jika `len` dimanipulasi oleh attacker, `%rsp` dapat dipaksa bertabrakan dengan data lain atau merusak memori frame sebelumnya (*Stack Clash Attack*).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Mengembalikan Pointer ke Local Stack Variable
```c
// FATAL: Mengembalikan alamat memori yang sudah dideallocasi
int* get_multiplier_table(void) {
    int local_table[4] = {10, 20, 30, 40};
    return local_table; // WARNING: function returns address of local variable
}
```
**Mekanisme Mesin:**
Begitu fungsi mengeksekusi `ret`, register `%rsp` dikembalikan ke posisi caller. Array `local_table` masih berada di memori fisik untuk sesaat, namun pemanggilan fungsi lain berikutnya akan segera **menimpa (*clobber*)** memori tersebut melalui operasi `push` baru.

**Solusi:**
```c
// Pendekatan 1: Caller-allocated buffer
void get_multiplier_table_safe(int *out_table, size_t size);

// Pendekatan 2: Dynamic allocation
int* get_multiplier_table_heap(void) {
    int *table = malloc(4 * sizeof(int));
    if (!table) return NULL;
    // ...
    return table;
}
```

### Kesalahan Fatal 2: Asumsi Optimasi Tail-Call pada Debug Build
Banyak engineer mengira rekursi mereka aman dari *Stack Overflow* karena telah ditulis dalam bentuk rekursi ekor (*tail-recursive*). Namun ketika dikompilasi dengan bendera debug standar (`gcc -O0 -g`), TCO dimatikan secara default. Aplikasi yang berjalan sempurna di lingkungan testing teroptimasi tiba-tiba mengalami *crash* saat dijalankan di server dengan image biner non-optimasi.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Standar MISRA C (Directive 17.2):**
    *Aturan Industri Otomotif dan Avionik:* *"Functions shall not call themselves, either directly or indirectly."* Rekursi dilarang keras dalam software kritis penerbangan (seperti standar DO-178C) karena determinisme kedalaman stack tidak dapat dibuktikan secara matematis tanpa kompleksitas pembuktian formal yang sangat tinggi.
2.  **Stack Probing (`-fstack-clash-protection`):**
    Gunakan opsi compiler GCC/Clang ini dalam produksi. Bendera ini memaksa CPU menyentuh (*probe*) setiap halaman memori 4KB saat mengalokasikan stack berukuran besar, mencegah kode penyerang melompati Guard Page tanpa terdeteksi.
3.  **Strict 16-Byte Stack Alignment Enforcing:**
    Ketika menulis fungsi stub assembly x86_64, pastikan jumlah instruksi `push` selalu seimbang atau selaraskan manual:
    ```assembly
    subq $8, %rsp   # Sesuaikan alignment jika instruksi call membutuhkan
    call external_c_func
    addq $8, %rsp   # Bersihkan alignment
    ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Pemanfaatan Branch Hints dan Instruksi Conditional Move

Pada alur kontrol bercabang, kegagalan prediksi cabang (*Branch Misprediction*) oleh sirkuit CPU menghasilkan *pipeline flush* yang membuang puluhan siklus clock (biasanya 15–20 cycles).

#### 1. Menggunakan Compiler Built-ins untuk Branch Prediction
```c
if (__builtin_expect(ptr == NULL, 0)) {
    // Alur penanganan kegagalan jarang terjadi (unlikely branch)
    handle_fatal_error();
}
```
Instruksi ini mengarahkan compiler untuk mengatur tata letak blok assembly sedemikian rupa sehingga alur yang paling mungkin dieksekusi diletakkan secara linier (*fall-through*), menghindari jump instruction.

#### 2. Menghilangkan Percabangan dengan Conditional Move (`cmov`)
Alih-alih menggunakan instruksi lompat bersyarat:
```assembly
    cmpq    %rsi, %rdi
    jle     .L_MIN
    movq    %rsi, %rax
    ret
.L_MIN:
    movq    %rdi, %rax
    ret
```
Gunakan instruksi tanpa cabang:
```assembly
    cmpq    %rsi, %rdi
    movq    %rsi, %rax
    cmovgq  %rdi, %rax   # Pindahkan %rdi ke %rax HANYA JIKA rdi > rsi
    ret
```
Instruksi `cmov` mengeksekusi logika bersyarat sepenuhnya di dalam pipeline tanpa mengubah `%rip`, sehingga secara fisik mustahil mengalami *branch misprediction*.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Anatomi Eksploitasi Stack-Smashing & Mitigasi Modern

Ketika sebuah fungsi mengalokasikan buffer lokal tanpa batas yang aman:
```c
void vulnerable(void) {
    char buffer[16];
    gets(buffer); // UNSAFE: Menulis data tanpa batas ke stack
}
```

```
Isi Memori Menuju Alamat Tinggi --->
[buffer (16B)] [Saved %rbp (8B)] [Saved %rip (8B)] [Caller's Data]
      |                                 ^
      +====== Overflow Menimpa =========+
```

Jika penyerang menyuntikkan payload lebih dari 24 byte, penyerang menimpa **Saved `%rip`** (Return Address). Saat `ret` dieksekusi, CPU melompat ke alamat acak yang ditentukan penyerang (misalnya payload shellcode atau Return-Oriented Programming (ROP) gadget).

### Pertahanan Modern:
1.  **Stack Canary (`-fstack-protector-strong`):**
    Compiler meletakkan nilai acak rahasia dari segment register thread (`%fs:0x28`) tepat di antara variabel lokal dan frame pointer sebelum eksekusi dimulai:
    ```assembly
    movq    %fs:40, %rax
    movq    %rax, -8(%rbp)       # Simpan canary di stack
    # ... eksekusi logika fungsi ...
    movq    -8(%rbp), %rax
    subq    %fs:40, %rax         # Verifikasi integritas canary
    jne     __stack_chk_fail     # CRASH seketika jika nilai berubah
    ```
2.  **Shadow Stack (Intel CET):**
    Fitur arsitektur perangkat keras modern yang mempertahankan stack internal kedua di memori tersembunyi yang hanya menyimpan return address. Ketika instruksi `ret` mendeteksi perbedaan antara Call Stack utama dan Shadow Stack, CPU memicu pengecualian *Control Protection Fault*.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Langkah-langkah investigasi forensik frame stack menggunakan **GDB (GNU Debugger)**.

### Skenario Debugging
Kompilasi program dengan informasi debug simbol:
```bash
gcc -g -O0 control_stack.c -o control_stack
gdb ./control_stack
```

### Investigasi Perintah GDB

1.  **Hentikan eksekusi pada fungsi rekursif:**
    ```gdb
    (gdb) break fibonacci_tail_rec
    (gdb) run
    ```

2.  **Periksa Status Register Pemanggilan:**
    ```gdb
    (gdb) info registers rsp rbp rip rdi rsi rdx
    rsp            0x7fffffffdce0      0x7fffffffdce0
    rbp            0x7fffffffdce0      0x7fffffffdce0
    rip            0x555555555149      0x555555555149 <fibonacci_tail_rec>
    rdi            0xa                 10 (Argumen 1: n)
    rsi            0x0                 0  (Argumen 2: a)
    rdx            0x1                 1  (Argumen 3: b)
    ```

3.  **Inspeksi Backtrace (Seluruh Frame Terdaftar):**
    ```gdb
    (gdb) continue
    (gdb) backtrace
    #0  fibonacci_tail_rec (n=9, a=1, b=1) at control_stack.c:16
    #1  0x00005555555551a3 in fibonacci_tail_rec (n=10, a=0, b=1) at control_stack.c:18
    #2  0x00005555555551dc in main () at control_stack.c:26
    ```

4.  **Dump Memori Raw Stack (Membaca Hexadecimal Langsung dari %rsp):**
    ```gdb
    (gdb) x/8xg $rsp
    0x7fffffffdca0: 0x00007fffffffdce0 0x00005555555551a3
    0x7fffffffdcb0: 0x0000000000000009 0x0000000000000001
    ```
    *Analisis Dump:*
    *   `0x00007fffffffdce0`: Merupakan *Saved `%rbp`* dari frame sebelumnya.
    *   `0x00005555555551a3`: Merupakan *Saved `%rip`* (Alamat instruksi pemanggil di fungsi sebelumnya).

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### System V AMD64 Calling Convention Reference
*   **Urutan Pengiriman Argumen:** `%rdi`, `%rsi`, `%rdx`, `%rcx`, `%r8`, `%r9`
*   **Return Value:** `%rax` (64-bit), `%rdx:%rax` (128-bit)
*   **Stack Pointer:** `%rsp` (Harus selalu sejajar 16-byte sebelum instruksi `call`)
*   **Frame Pointer:** `%rbp` (Opsional jika `-fomit-frame-pointer` aktif)

### Assembly Instructions Quick Reference
*   `push S` $\rightarrow$ `sub $8, %rsp; mov S, (%rsp)`
*   `pop D` $\rightarrow$ `mov (%rsp), D; add $8, %rsp`
*   `call Label` $\rightarrow$ `push %rip; jmp Label`
*   `ret` $\rightarrow$ `pop %rip`
*   `leave` $\rightarrow$ `mov %rbp, %rsp; pop %rbp`

### Kondisi Percabangan Populer
*   `test %rax, %rax`: Menguji nilai register itu sendiri (berguna untuk validasi pointer `NULL` atau integer `0` tanpa modifikasi operand).
*   `cmp A, B`: Memperbarui flag CPU berdasarkan operasi $B - A$.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa yang terjadi secara fisik pada hardware register saat instruksi `call` dieksekusi?**
   * A. Register `%rsp` ditambah 8 byte dan alamat register `%rax` dipanggil.
   * B. Register `%rip` ditambah nilai offset seketika tanpa modifikasi stack.
   * C. Alamat instruksi berikutnya (*Return Address*) di-*push* ke stack memori dan register `%rip` diisi dengan alamat tujuan pemanggilan.
   * D. Seluruh general-purpose register disalin ke memori cache L1.
   <details><summary>Jawaban & Penjelasan</summary>**Jawaban: C**. Instruksi `call` secara atomik mendorong isi register `%rip` saat ini (yang menunjuk ke instruksi setelah `call`) ke alamat memori yang ditunjuk `%rsp` (setelah decrement 8 byte), lalu melompat ke alamat target fungsi.</details>

2. **Ke arah mana alamat memori berkembang saat stack frame baru dialokasikan pada arsitektur x86_64?**
   * A. Ke arah alamat yang lebih tinggi (*Ascending* / Upward).
   * B. Ke arah alamat yang lebih rendah (*Descending* / Downward).
   * C. Acak, ditentukan oleh kernel memory allocator.
   * D. Bergantung pada urutan deklarasi variabel di kode C.
   <details><summary>Jawaban & Penjelasan</summary>**Jawaban: B**. Pada arsitektur x86_64, stack tumbuh dari alamat memori tinggi menuju alamat memori rendah. Setiap operasi `push` atau `sub $N, %rsp` menurunkan nilai angka register `%rsp`.</details>

3. **Register manakah yang bertindak sebagai pemegang Return Value pertama untuk tipe data integer atau pointer di Linux x86_64?**
   * A. `%rdi`
   * B. `%rsp`
   * C. `%rax`
   * D. `%rbx`
   <details><summary>Jawaban & Penjelasan</summary>**Jawaban: C**. Sesuai standar System V AMD64 ABI, register `%rax` digunakan untuk mengembalikan nilai integer dan pointer dengan panjang hingga 64-bit.</details>

4. **Apa yang dimaksud dengan konsep "Leaf Function" dalam kompilasi assembly?**
   * A. Fungsi yang tidak menerima argumen apapun.
   * B. Fungsi yang tidak pernah memanggil fungsi lain di dalam tubuhnya.
   * C. Fungsi rekursif tanpa basis terminasi.
   * D. Fungsi yang mengembalikan pointer ke struktur linked list.
   <details><summary>Jawaban & Penjelasan</summary>**Jawaban: B**. Leaf Function adalah simpul daun dalam Call Graph sistem; fungsi ini tidak pernah memanggil fungsi lain. Compiler dapat mengoptimasi Leaf Function secara drastis, sering kali tanpa membuat stack frame baru dan memanfaatkan Red Zone.</details>

5. **Instruksi x86 manakah yang setara fungsinya dengan gabungan instruksi `mov %rbp, %rsp` diikuti dengan `pop %rbp`?**
   * A. `ret`
   * B. `enter`
   * C. `leave`
   * D. `halt`
   <details><summary>Jawaban & Penjelasan</summary>**Jawaban: C**. Instruksi `leave` didesain khusus oleh perancang arsitektur x86 untuk membersihkan stack frame secara cepat pada *function epilogue*, memulihkan `%rsp` ke posisi `%rbp`, lalu memulihkan frame pointer Caller lama melalui `pop`.</details>

---

### Soal Tingkat Menengah (Intermediate)

6. **Mengapa aturan ABI System V mewajibkan alignment `%rsp` kelipatan 16-byte tepat sebelum instruksi `call`?**
   * A. Agar prosesor dapat mengeksekusi instruksi jumping lebih cepat.
   * B. Untuk memastikan instruksi SIMD/SSE/AVX yang mengakses stack (seperti `movaps`) tidak memicu General Protection Fault (#GP).
   * C. Untuk menyisakan ruang bagi kernel syscall number.
   * D. Karena memori fisik RAM hanya dapat membaca kelipatan 16 byte.
   <details><summary>Jawaban & Penjelasan</summary>**Jawaban: B**. Banyak instruksi floating-point dan SIMD modern (seperti Streaming SIMD Extensions / SSE) mensyaratkan alamat data bersejajar 16-byte untuk efisiensi transfer data internal. Pelanggaran alignment ini akan memicu hardware exception.</details>

7. **Apa peran utama dari area 128-byte yang disebut "Red Zone" pada x86_64 System V ABI?**
   * A. Area isolasi untuk mendeteksi serangan malware secara real-time.
   * B. Ruang scratchpad di bawah `%rsp` yang dapat digunakan Leaf Function tanpa harus memodifikasi nilai pointer `%rsp`.
   * C. Tempat penyimpanan variabel global program.
   * D. Area reservasi khusus untuk penanganan interrupt OS kernel secara langsung.
   <details><summary>Jawaban & Penjelasan</summary>**Jawaban: B**. Red Zone adalah optimasi compiler ABI yang memungkinkan fungsi tidak membuang siklus clock untuk instruksi `subq` dan `addq` pada `%rsp` jika alokasi ruang lokalnya $\le 128$ byte dan tidak memanggil fungsi lain.</details>

8. **Transformasi fisik apa yang dilakukan compiler ketika menerapkan Tail-Call Optimization (TCO) pada sebuah fungsi rekursif?**
   * A. Mengganti tipe data variabel lokal menjadi global.
   * B. Mengalokasikan stack frame secara dinamis di Heap via `malloc`.
   * C. Mengubah instruksi pemanggilan `call` menjadi instruksi pembaruan register dan lompatan lokal tak bersyarat (`jmp`).
   * D. Menyimpan seluruh nilai variabel ke dalam register SSE.
   <details><summary>Jawaban & Penjelasan</summary>**Jawaban: C**. TCO mendeteksi bahwa tidak ada operasi lanjutan setelah rekursi mengembalikan nilai. Compiler mendaur ulang frame saat ini dengan membarui register argumen dan melompat kembali ke awal fungsi via `jmp`, meniadakan penambahan stack frame.</details>

9. **Jika sebuah program C mengalami *Segmentation Fault* pada baris instruksi `push %rbp`, apa kemungkinan penyebab paling mendasar di tingkat arsitektur?**
   * A. Program mengeksekusi instruksi pembagian dengan nilai nol.
   * B. Stack Pointer (`%rsp`) telah tumbuh melampaui batas batas virtual memory stack yang sah dan mencoba menulis ke Guard Page yang tidak terpetakan.
   * C. Register `%rbp` kehilangan nilai pointer aslinya.
   * D. Instruksi cache prosesor mengalami kegagalan transmisi.
   <details><summary>Jawaban & Penjelasan</summary>**Jawaban: B**. Instruksi `push` mencoba menulis ke alamat `[%rsp - 8]`. Jika memori stack telah mencapai limit yang ditetapkan kernel OS, alamat tersebut berada pada Guard Page (tanpa atribut penulisan), memicu hardware page fault yang bermuara pada `SIGSEGV`.</details>

10. **Perhatikan cuplikan assembly berikut:**
    ```assembly
    testq %rdi, %rdi
    cmovz %rsi, %rax
    ```
    **Kapan register `%rax` akan diperbarui dengan nilai dari `%rsi`?**
    * A. Hanya jika nilai register `%rdi` bernilai bukan nol.
    * B. Hanya jika nilai register `%rdi` bernilai nol.
    * C. Kapan saja secara berulang tanpa syarat.
    * D. Hanya jika nilai register `%rsi` lebih besar dari `%rdi`.
    <details><summary>Jawaban & Penjelasan</summary>**Jawaban: B**. Instruksi `testq %rdi, %rdi` menjalankan operasi logika AND bit-demi-bit antara `%rdi` dan dirinya sendiri. Jika `%rdi == 0`, maka Zero Flag (`ZF`) disetel menjadi 1. Instruksi `cmovz` (*Conditional Move if Zero*) akan menyalin `%rsi` ke `%rax` hanya jika `ZF == 1`.</details>

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Proyek
Buatlah sebuah program C modular yang mengimplementasikan **Recursive Descent Expression Evaluator** sederhana yang mampu memparsing dan mengevaluasi operasi matematika string bertanda kurung (contoh: `"(10 + (20 * (30 - 5)))"`).

### Persyaratan Proyek:
1.  **Detektor Kedalaman Stack (Stack Depth Guard):**
    Anda harus mengimplementasikan fungsi inspeksi alamat stack dinamis.
    ```c
    void* get_stack_pointer(void);
    bool check_stack_safety(void *base_stack_addr, size_t threshold_bytes);
    ```
    *Petunjuk:* Baca nilai `%rsp` menggunakan *Inline Assembly* GNU C (`__asm__ __volatile__`).
2.  **Proteksi Anti-Crash:**
    Jika kedalaman ekspresi yang dievaluasi mendekati margin bahaya (misal: stack tumbuh lebih dari 64 Kilobyte dari base frame fungsi `main`), parser harus menggugurkan parsing secara terhormat (*graceful exit*) dengan kode error `ERROR_STACK_OVERFLOW_RISK`, tanpa membiarkan sistem operasi melempar `SIGSEGV`.
3.  **Verifikasi dengan Assembly:**
    Kompilasi kode Anda dengan parameter `-S -fverbose-asm` dan verifikasi secara visual bagaimana *Stack Depth Guard* disisipkan oleh compiler ke dalam *prologue* atau *body* fungsi Anda.