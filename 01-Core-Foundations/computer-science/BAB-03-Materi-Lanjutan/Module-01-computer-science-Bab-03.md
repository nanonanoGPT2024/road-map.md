# Kurikulum Computer Science: 01-Core-Foundations
# Bab 03: Arsitektur Sistem Komputer & Sistem Operasi
## Modul 01: Sistem Operasi & Manajemen Proses

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** CS-CF-03-01
* **Nama Modul:** Sistem Operasi & Manajemen Proses
* **Kategori:** 01-Core-Foundations
* **Prasyarat Pengetahuan:**
  * Pemrograman Bahasa C tingkat menengah (pointer, manipulasi memori, struct).
  * Arsitektur Komputer Dasar (register CPU, Instruction Pointer/Program Counter, stack vs heap, interupsi perangkat keras).
* **Alokasi Waktu Teori & Praktek:** 12 Jam (6 Jam Analisis Teori & Mekanisme Kernel, 6 Jam Hands-on Systems Programming).
* **Tingkat Kesulitan:** Intermediate / Advanced Undergraduate.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Mekanisme Eksekusi Kernel vs User Mode:** Menguraikan batas perlindungan perangkat keras (*hardware privilege rings*), transisi status CPU melalui instruksi interupsi perangkat lunak (*software interrupt/sysenter/syscall*), serta pemulihan konteks eksekusi (*iret/sysret*).
2. **Mendekonstruksi Anatomi Process Control Block (PCB):** Menjelaskan representasi status proses di tingkat kernel (seperti `struct task_struct` pada kernel Linux), termasuk isolasi ruang alamat virtual, deskriptor berkas, dan konteks register.
3. **Mengimplementasikan Siklus Hidup Proses POSIX:** Memprogram orkestrasian proses menggunakan primitives sistem operasi Unix/Linux (`fork()`, `execve()`, `waitpid()`, `exit()`), termasuk penanganan skenario *zombie* dan *orphan processes*.
4. **Mengevaluasi Kinerja Context Switching:** Mengukur dan membedah *overhead* pergantian konteks proses dan thread, termasuk biaya langsung (*register save/restore*, pergantian tabel halaman / manipulasi register `CR3`) dan biaya tidak langsung (*TLB invalidation*, *cache cold-misses*).
5. **Membangun Sistem Manajemen Subproses yang Kuat:** Merancang komponen pemantau proses (*process supervisor*) yang tahan terhadap kegagalan dengan pemanfaatan penanganan sinyal asinkron (*asynchronous signal safety*) dan IPC (*Inter-Process Communication*) tingkat rendah.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
Sistem Operasi (Manajer Sumber Daya & Isolasi Abstraksi)
 ├── Batas Perlindungan (Hardware Protection Boundaries)
 │    ├── Ring 0 (Kernel Mode) vs Ring 3 (User Mode)
 │    └── System Call Interface (Mekanisme Trap / Syscall Instruction)
 │
 ├── Abstraksi Proses (The Process Abstraction)
 │    ├── Ruang Alamat Virtual (Text, Data, BSS, Heap, Stack)
 │    ├── Process Control Block (PCB / Linux task_struct)
 │    │    ├── PID, PPID, Kredensial
 │    │    ├── Status Eksekusi (Running, Ready, Blocked, Zombie)
 │    │    ├── File Descriptor Table
 │    │    └── Konteks Arsitektural (CPU Registers, Memory Maps)
 │    └── State Machine Siklus Hidup Proses (Five/Seven-State Model)
 │
 ├── Orkestrasi Proses (POSIX Lifecycle Management)
 │    ├── Duplikasi Ruang Alamat (fork() via Copy-on-Write)
 │    ├── Penggantian Image Eksekusi (Keluarga exec())
 │    ├── Sinkronisasi Penundaan & Penuaian Status (waitpid())
 │    └── Penanganan Sinyal & Terminasi (Signals, exit(), SIGCHLD)
 │
 └── Mekanika Context Switch
      ├── Penanganan Interupsi Timer (Preemptive Scheduling)
      ├── Penyimpanan & Pemulihan State (Register Preservation)
      └── Pergantian Ruang Alamat (MMU Page Directory Swap)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

1. **Ilusi Konkurensi pada Perangkat Keras Tunggal:** Proses adalah abstraksi fundamental yang memungkinkan CPU fisik tunggal menjalankan ratusan program secara bersamaan melalui teknik *time-sharing* tanpa saling mengorbankan integritas data.
2. **Isolasi Keamanan dan Keandalan:** Tanpa pemisahan proses dan mode eksekusi perangkat keras, *bug* atau eksploitasi dalam sebuah aplikasi tingkat pengguna (seperti web browser) dapat memanipulasi ruang alamat kernel, menulis ulang firmware, atau membaca data rahasia dari aplikasi lain.
3. **Optimasi Rekayasa Perangkat Lunak Skala Besar:** Memahami perbedaan mendalam antara *process* dan *thread*, serta biaya intrinsik dari sebuah *context switch*, adalah dasar penentuan arsitektur sistem berperforma tinggi—seperti model *event-driven* (Node.js, Nginx) versus model *worker-thread/process-pool* (PostgreSQL, Apache).
4. **Debugging Masalah Sistemik Kompleks:** Kegagalan infrastruktur seperti *resource leak*, penumpukan *zombie processes*, *deadlock*, hingga *CPU throttling* yang tidak dapat dijelaskan hanya dapat dipecahkan jika perekayasa memahami cara kerja scheduler kernel dan penanganan tabel deskriptor.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Definisi Proses vs Program
Sebuah **program** adalah entitas pasif, berupa berkas biner berekstensi tertentu (misalnya format ELF pada Linux, Mach-O pada macOS, atau PE pada Windows) yang tersimpan di media penyimpanan sekunder, berisi urutan instruksi mesin dan data statis. 

Sebuah **proses** adalah entitas aktif: sebuah program yang sedang dieksekusi di dalam memori, lengkap dengan sumber daya yang dialokasikan oleh kernel. Sebuah proses mencakup:
* **Ruang Alamat Virtual (Virtual Address Space):** Berisi kode biner (*text segment*), variabel global terinisialisasi (*data segment*), variabel global tak terinisialisasi (*BSS segment*), alokasi memori dinamis (*heap*), dan frame fungsi lokal (*call stack*).
* **Konteks CPU (Processor Context):** Nilai dari Program Counter (PC / Instruction Pointer), Stack Pointer (SP), register serbaguna (*general-purpose registers*), dan register status (FLAGS).
* **Konteks Kernel:** Deskriptor berkas yang terbuka, soket jaringan, pengidentifikasi keamanan (UID, GID), status sinyal, dan kuota sumber daya.

### 2. Dual-Mode Operation: User Mode vs Kernel Mode
Arsitektur prosesor modern (seperti x86_64 atau ARMv8) menerapkan sistem berbasis *privilege levels* (cincin proteksi):
* **User Mode (Ring 3 pada x86_64, EL0 pada ARM):** CPU membatasi instruksi tertentu yang berpotensi merusak sistem. Instruksi seperti manipulasi tabel halaman, menonaktifkan interupsi hardware (`CLI`), atau mengakses port I/O secara langsung akan memicu pelanggaran proteksi (*General Protection Fault*).
* **Kernel Mode (Ring 0 pada x86_64, EL1 pada ARM):** CPU memiliki kontrol tanpa batas terhadap perangkat keras, instruksi istimewa, memori fisik, dan konfigurasi CPU.

Transisi dari User Mode ke Kernel Mode dilakukan melalui mekanisme terkendali:
1. **Interrupts:** Sinyal asinkron dari perangkat keras (misal: keyboard, timer chip, kartu jaringan).
2. **Exceptions/Traps:** Sinyal sinkron akibat kesalahan internal eksekusi (misal: *division by zero*, *page fault*).
3. **System Calls:** Permintaan terencana dari aplikasi user ke kernel menggunakan instruksi khusus seperti `syscall` (x86_64) atau `svc` (ARM).

### 3. Process Control Block (PCB)
Kernel melacak setiap proses menggunakan struktur data yang disebut **Process Control Block (PCB)**. Pada Linux, PCB direpresentasikan oleh `struct task_struct` (didefinisikan dalam `<linux/sched.h>`). Elemen-elemen kritis di dalamnya meliputi:
* **Identifier:** `pid_t pid` (Process ID), `pid_t tgid` (Thread Group ID), `struct task_struct *parent`.
* **State:** State proses saat ini (misalnya `TASK_RUNNING`, `TASK_INTERRUPTIBLE`, `EXIT_ZOMBIE`).
* **Kredensial:** UID, GID, capability sets.
* **Informasi Memori:** Pointer ke `struct mm_struct`, yang memetakan deskriptor *Virtual Memory Areas* (VMA) dan Page Table Base Register (`CR3` pada x86_64).
* **File Management:** Pointer ke `struct files_struct`, yang memuat tabel array deskriptor berkas aktif (`fd table`).
* **CPU Context:** Tempat penyimpanan register register CPU saat proses tidak sedang terjadwal pada inti CPU (disimpan dalam `struct thread_struct`).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Siklus Hidup Proses (Process State Transitions)
Kernel mengatur transisi proses menggunakan model status (*state machine*):

```
+------------+       (Alokasi PCB & Memory)
|    NEW     | ----------------------------------+
+------------+                                   |
                                                 v
  +----------> +------------+   Scheduler Dispatch  +------------+
  |            |   READY    | --------------------> |  RUNNING   |
  |            +------------+                       +------------+
  |              ^        ^                            |       |
  |              |        |                            |       |
  | Timer Expire |        +-- I/O Selesai / Event -----+       |
  | (Preemption) |                                     |       |
  +--------------+                                     |       | System Call /
                                                       |       | I/O Request
                                                       v       v
                                                +------------+ |
                                                |  BLOCKED/  | |
                                                |  WAITING   | |
                                                +------------+ |
                                                               |
                                            Proses Selesai /   |
                                            Terminasi Fatal    |
                                                               v
                                                        +------------+
                                                        | TERMINATED |
                                                        |  (ZOMBIE)  |
                                                        +------------+
```

1. **NEW:** Proses sedang dibentuk melalui alokasi PCB dan struktur awal.
2. **READY:** Proses memiliki seluruh sumber daya yang diperlukan, dimasukkan ke dalam antrean penjadwalan (*runqueue*), dan menunggu jatah eksekusi CPU dari *scheduler*.
3. **RUNNING:** Instruksi-instruksi proses dieksekusi secara fisik di atas inti CPU.
4. **BLOCKED (WAITING):** Proses terhenti menunggu operasi I/O atau sinkronisasi (misalnya mutex lock). Proses dikeluarkan dari *runqueue* agar tidak membuang siklus CPU.
5. **TERMINATED (ZOMBIE):** Proses telah menyelesaikan tugasnya (`exit()`), sebagian besar memori dan sumber dayanya telah dibebaskan, tetapi PCB-nya tetap dipertahankan agar proses induk (*parent*) dapat membaca kode keluaran (*exit code*).

### 2. Mekanisme Fork-Exec-Wait
Model pembuatan proses pada sistem operasi keluarga Unix tidak membuat proses baru dari nol, melainkan menggunakan pola kloning:

```
Process P (Parent)                Kernel Space               Process C (Child)
      |                                |                             |
      |-- fork() --------------------->| (Duplikasi PCB, VMA,        |
      |                                |  Set page table RO (COW))   |
      |<-- return child_pid            |---------------------------->|
      |                                |           return 0          |
      |-- waitpid(child_pid)           |                             |-- execve("/bin/ls")
      |   (P suspended)                |                             |   (Replace Address Space)
      |                                |                             |   (Load ELF segments)
      |                                |                             |-- main() of /bin/ls
      |                                |                             |
      |                                |                             |-- exit(0)
      |                                | (Free memory, keep Zombie)  |
      |                                |<----------------------------|
      |<-- SIGCHLD / Wake up ----------|                             X (Terminated)
      |-- reap exit status             | (Destroy PCB)
      v                                v
```

* **`fork()`:** Mengkloning proses pemanggil. Melalui optimasi **Copy-On-Write (COW)**, kernel tidak langsung menyalin seluruh memori fisik. Kernel menyalin tabel halaman (*page table*) milik parent ke child, lalu menandai seluruh halaman memori fisik sebagai *Read-Only*. Jika salah satu proses menulis ke halaman tersebut, CPU memicu pengecualian *Page Fault*. Kernel kemudian menginterupsi eksekusi, mengalokasikan satu *frame* memori baru untuk halaman tersebut, menyalin isinya, menandainya sebagai *Read-Write*, dan melanjutkan eksekusi.
* **`execve()`:** Menghancurkan ruang alamat virtual proses saat ini. Kernel membongkar segment *text*, *data*, *heap*, dan *stack* yang lama, lalu membaca berkas biner format ELF baru dari sistem penyimpanan, memetakan segment-segment biner baru tersebut ke dalam ruang alamat proses, lalu menginisialisasi Program Counter ke titik masuk (*entry point*) executable baru tersebut (biasanya fungsi `_start`).
* **`waitpid()`:** Menangguhkan eksekusi parent sampai child dengan PID tertentu berganti status (misalnya keluar). Fungsi ini mengembalikan nilai status terminasi dan memicu kernel untuk membersihkan PCB child yang berstatus *zombie*.

### 3. Anatomi Context Switch
*Context Switch* terjadi ketika penjadwal kernel menghentikan eksekusi suatu proses dan menggantinya dengan proses lain:

1. **Pemicu:** Interupsi hardware dari timer (misalnya Local APIC timer yang menandakan kuantum waktu habis) atau instruksi penyerahan CPU sukarela (seperti I/O blocking atau `sched_yield()`).
2. **Penyimpanan State Arsitektur:** Kernel menyimpan register-register CPU (`%rax`, `%rbx`, `%rsp`, `%rip`, register segmen, register floating point/AVX) milik proses yang keluar ke dalam kernel stack proses tersebut.
3. **Transisi Penjadwalan:** Scheduler memilih proses baru dari *runqueue* (misalnya menggunakan algoritma Completely Fair Scheduler / CFS pada Linux).
4. **Pembaruan Konteks Memori (Jika berganti proses, bukan thread):**
   * Kernel memuat alamat fisik direktori tabel halaman proses baru ke register kontrol CPU (pada x86_64: `mov %rdi, %cr3`).
   * Pergantian nilai `CR3` secara implisit menyebabkan penghapusan entri (*flush*) pada sebagian besar **Translation Lookaside Buffer (TLB)**, kecuali entri yang ditandai *Global*. Hal ini memicu *TLB miss storm* pada siklus eksekusi awal proses baru.
5. **Pemulihan State:** Kernel memuat kembali nilai-nilai register proses baru dari kernel stack miliknya, menyetel stack pointer CPU (`%rsp`) ke stack proses baru, dan mengeksekusi instruksi pemulihan (`iretq` atau `sysretq`).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Struktur Ruang Alamat Virtual Proses 64-bit (Linux x86_64)

```
0xFFFFFFFFFFFFFFFF +---------------------------------------------+
                   |                KERNEL SPACE                 |
                   | (Hanya dapat diakses melalui Kernel Mode)   |
0xFFFF800000000000 +---------------------------------------------+
                   |                 TIDAK VALID                 |
                   |               (Canonical Hole)              |
0x00007FFFFFFFFFFF +---------------------------------------------+
                   | User Stack                                  |
                   | - Variabel lokal, frame fungsi              |
                   | - Tumbuh ke bawah (Downwards)               |
                   |                 |                           |
                   |                 v                           |
                   + - - - - - - - - - - - - - - - - - - - - - - +
                   |                                             |
                   | Pustaka Dinamis Terpetakan (Shared Libs)    |
                   | (libc.so, libpthread.so via mmap)           |
                   |                                             |
                   + - - - - - - - - - - - - - - - - - - - - - - +
                   |                 ^                           |
                   |                 |                           |
                   | Heap (Alokasi dinamis via malloc / brk)     |
                   | - Tumbuh ke atas (Upwards)                  |
                   +---------------------------------------------+
                   | BSS Segment                                 |
                   | - Variabel global tak terinisialisasi        |
                   | - Dinolkan oleh kernel (Zero-filled)        |
                   +---------------------------------------------+
                   | Data Segment                                |
                   | - Variabel global terinisialisasi           |
                   +---------------------------------------------+
                   | Text Segment                                |
                   | - Instruksi mesin biner executable          |
                   | - Hak akses: Read-Only, Execute             |
0x0000000000400000 +---------------------------------------------+
                   | Akses Terlarang / Null Pointer Trap Zone    |
0x0000000000000000 +---------------------------------------------+
```

### 2. Urutan Detail Context Switch antara Dua Proses

```
   PROSES A (User)            KERNEL (Core OS)            PROSES B (User)
       |                             |                           |
  (1)  | Menjalankan instruksi       |                           |
       |                             |                           |
       |--- Hardware Timer Tick ---->|                           |
       |    (Interrupt Trap Ring 0)  | (2) CPU beralih Ring 0    |
       |                             |     Simpan %rsp, %rip A   |
       |                             |     ke Kernel Stack A     |
       |                             |                           |
       |                             | (3) Eksekusi Interrupt    |
       |                             |     Handler (do_IRQ)      |
       |                             |                           |
       |                             | (4) Panggil schedule()    |
       |                             |     Pilih Proses B        |
       |                             |                           |
       |                             | (5) switch_to(A, B):      |
       |                             |     - Simpan sisa callee- |
       |                             |       saved registers A   |
       |                             |     - Ganti Kernel Stack  |
       |                             |       Pointer ke Stack B  |
       |                             |     - Tulis CR3 = B.pgdir |
       |                             |       (TLB Flush terjadi) |
       |                             |     - Muat register B     |
       |                             |                           |
       |                             | (6) sysret / iretq        |
       |                             |-------------------------->| (7) CPU beralih Ring 3
       |                             |                           |     Mulai jalankan B
       |                             |                           |     pada %rip B
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah program C yang mendemonstrasikan hierarki proses, alokasi memori independen via `fork()`, pemanfaatan instruksi penggantian `execvp()`, serta mekanisme sinkronisasi parent menggunakan `waitpid()`.

```c
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>

int main(void) {
    pid_t pid;
    int shared_state = 42;

    printf("[Parent] Menginisialisasi proses utama (PID: %d)\n", getpid());

    pid = fork();

    if (pid < 0) {
        // fork() mengembalikan angka negatif jika terjadi kegagalan sistem
        perror("Gagal melakukan fork");
        return EXIT_FAILURE;
    }

    if (pid == 0) {
        // Cabang Proses Anak (Child)
        printf("[Child] Berhasil dibentuk (PID: %d, Parent PID: %d)\n", getpid(), getppid());
        
        // Membuktikan isolasi memori: Modifikasi variabel tidak berdampak pada parent
        shared_state += 100;
        printf("[Child] Nilai shared_state termodifikasi: %d\n", shared_state);

        printf("[Child] Mengganti image biner dengan '/bin/echo' via execvp...\n");
        char *args[] = {"echo", "[Exec]", "Halo dari biner baru yang dieksekusi!", NULL};
        
        execvp(args[0], args);

        // Baris di bawah HANYA dieksekusi jika execvp() mengalami kegagalan
        perror("[Child] Gagal mengeksekusi execvp");
        _exit(EXIT_FAILURE);
    } else {
        // Cabang Proses Induk (Parent)
        int status;
        printf("[Parent] Menunggu terminasi child process (Child PID: %d)...\n", pid);

        // Menunggu secara eksplisit hingga child selesai agar tidak menjadi zombie
        pid_t terminated_child = waitpid(pid, &status, 0);

        if (terminated_child == -1) {
            perror("[Parent] Terjadi error pada waitpid");
            return EXIT_FAILURE;
        }

        // Memeriksa status terminasi anak
        if (WIFEXITED(status)) {
            printf("[Parent] Child %d selesai secara normal dengan status keluar: %d\n",
                   terminated_child, WEXITSTATUS(status));
        } else if (WIFSIGNALED(status)) {
            printf("[Parent] Child %d dibunuh oleh sinyal: %d\n",
                   terminated_child, WTERMSIG(status));
        }

        // Membuktikan ruang alamat parent tidak terpengaruh manipulasi memori child
        printf("[Parent] Nilai shared_state pada parent tetap: %d\n", shared_state);
    }

    return EXIT_SUCCESS;
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Di sistem produksi, arsitektur seperti *worker pool* atau *process supervisor* (contoh: implementasi sederhana dari Nginx Master Process atau Unicorn) harus mampu menangani sinyal kernel secara *asynchronous-safe*, memonitor worker yang mati mendadak, merekonstruksi worker baru (*self-healing*), serta membersihkan status zombie tanpa blocking.

Kode berikut mengimplementasikan sebuah **Robust Process Supervisor** yang mematuhi standar POSIX:

```c
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <errno.h>
#include <stdbool.h>
#include <string.h>

#define MAX_WORKERS 3

typedef struct {
    pid_t pid;
    int worker_index;
    bool is_active;
} WorkerSlot;

static WorkerSlot worker_pool[MAX_WORKERS];
static volatile sig_atomic_t shutdown_requested = 0;
static volatile sig_atomic_t child_status_changed = 0;

// Handler sinyal: Harus bersifat async-signal-safe (menghindari fungsi I/O standar seperti printf)
static void handle_sigchld(int sig) {
    (void)sig;
    child_status_changed = 1;
}

static void handle_sigterm(int sig) {
    (void)sig;
    shutdown_requested = 1;
}

// Logika pekerjaan yang dijalankan oleh worker
static void run_worker_loop(int index) {
    printf("[Worker %d | PID: %d] Memulai siklus kerja...\n", index, getpid());
    
    // Simulasikan variasi waktu kerja sebelum terminasi acak
    srand(getpid());
    int work_cycles = 2 + (rand() % 4);
    
    for (int i = 0; i < work_cycles; i++) {
        sleep(1);
    }

    // Simulasikan kemungkinan crash (50% crash via SIGSEGV, 50% exit normal)
    if (rand() % 2 == 0) {
        printf("[Worker %d | PID: %d] Mengalami fatal crash (simulasi)...\n", index, getpid());
        int *bad_ptr = NULL;
        *bad_ptr = 42; // Memicu SIGSEGV
    }

    printf("[Worker %d | PID: %d] Selesai secara anggun.\n", index, getpid());
    _exit(EXIT_SUCCESS);
}

// Meluncurkan satu unit worker baru
static void spawn_worker(int index) {
    pid_t pid = fork();

    if (pid < 0) {
        perror("[Master] Gagal fork worker baru");
        return;
    }

    if (pid == 0) {
        // Reset sinyal handler pada level anak
        signal(SIGCHLD, SIG_DFL);
        signal(SIGTERM, SIG_DFL);
        run_worker_loop(index);
    } else {
        worker_pool[index].pid = pid;
        worker_pool[index].worker_index = index;
        worker_pool[index].is_active = true;
        printf("[Master] Berhasil membangkitkan Worker %d dengan PID: %d\n", index, pid);
    }
}

// Memanen worker yang mati tanpa memblokir siklus utama (Anti-Zombie)
static void reap_dead_workers(void) {
    int status;
    pid_t pid;

    // Gunakan WNOHANG agar non-blocking. Loop sampai semua child yang mati terambil
    while ((pid = waitpid(-1, &status, WNOHANG)) > 0) {
        for (int i = 0; i < MAX_WORKERS; i++) {
            if (worker_pool[i].is_active && worker_pool[i].pid == pid) {
                worker_pool[i].is_active = false;
                
                if (WIFEXITED(status)) {
                    printf("[Master] Deteksi: Worker %d (PID: %d) keluar normal dengan kode %d.\n", 
                           i, pid, WEXITSTATUS(status));
                } else if (WIFSIGNALED(status)) {
                    printf("[Master] PERINGATAN: Worker %d (PID: %d) mati abnormal akibat sinyal %d (%s).\n", 
                           i, pid, WTERMSIG(status), strsignal(WTERMSIG(status)));
                }

                // Self-healing: Bangkitkan pengganti jika master tidak sedang fase shutdown
                if (!shutdown_requested) {
                    printf("[Master] Melakukan self-healing untuk slot %d...\n", i);
                    spawn_worker(i);
                }
                break;
            }
        }
    }
}

int main(void) {
    printf("[Master] Memulai Supervisor Daemon (PID: %d)\n", getpid());

    // Daftarkan signal handler
    struct sigaction sa_chld, sa_term;
    memset(&sa_chld, 0, sizeof(sa_chld));
    sa_chld.sa_handler = handle_sigchld;
    sigemptyset(&sa_chld.sa_mask);
    sa_chld.sa_flags = SA_RESTART | SA_NOCLDSTOP;
    sigaction(SIGCHLD, &sa_chld, NULL);

    memset(&sa_term, 0, sizeof(sa_term));
    sa_term.sa_handler = handle_sigterm;
    sigemptyset(&sa_term.sa_mask);
    sigaction(SIGTERM, &sa_term, NULL);
    sigaction(SIGINT, &sa_term, NULL);

    // Initial spawning
    for (int i = 0; i < MAX_WORKERS; i++) {
        spawn_worker(i);
    }

    // Event Loop Supervisor
    while (!shutdown_requested) {
        if (child_status_changed) {
            child_status_changed = 0;
            reap_dead_workers();
        }
        // Suspensi hingga ada sinyal baru untuk efisiensi CPU
        pause();
    }

    // Graceful Shutdown Phase
    printf("\n[Master] Menerima instruksi terminasi. Menghentikan seluruh worker...\n");
    for (int i = 0; i < MAX_WORKERS; i++) {
        if (worker_pool[i].is_active) {
            kill(worker_pool[i].pid, SIGTERM);
        }
    }

    // Menunggu seluruh worker terminasi total sebelum master keluar
    printf("[Master] Menunggu pembersihan seluruh child...\n");
    while (wait(NULL) > 0 || errno != ECHILD) {
        // Loop terminasi
    }

    printf("[Master] Seluruh child berhasil dipanen. Supervisor ditutup secara aman.\n");
    return EXIT_SUCCESS;
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektural | Multi-Process (Misal: PostgreSQL, Nginx) | Multi-Threaded (Misal: MySQL, JVM) |
| :--- | :--- | :--- |
| **Isolasi Memori & Keamanan** | **Tinggi:** Setiap proses memiliki ruang alamat virtual terpisah. *Memory corruption* atau segfault di satu proses tidak menghancurkan proses lain. | **Rendah:** Semua thread berbagi *virtual memory space* yang sama. Satu *wild pointer* atau segfault meruntuhkan seluruh instance program. |
| **Overhead Context Switch** | **Tinggi:** Melibatkan penggantian direktori tabel halaman (`CR3`), membersihkan entri TLB (*TLB Flush*), menyebabkan tingginya *cache misses*. | **Rendah:** Tabel halaman tetap dipertahankan; TLB tidak di-*flush*. CPU hanya menukar register konteks dan stack pointer. |
| **Kompleksitas Komunikasi (IPC)** | **Kompleks:** Memerlukan mekanisme IPC terpisah (Unix Domain Sockets, Pipes, Shared Memory, Message Queues) dan serialisasi data. | **Sederhana:** Cukup mereferensikan memori yang sama. Namun memerlukan primitif sinkronisasi (*Mutex, RWLock, Condition Variables*). |
| **Biaya Alokasi Sumber Daya** | **Tinggi:** Duplikasi deskriptor berkas, struktur PCB kernel, dan tabel alokasi memori halaman (*Page Tables*). | **Rendah:** Hanya memerlukan alokasi Stack baru (biasanya 2–8 MB) dan Thread Control Block (TCB) minimal. |
| **Skalabilitas Multi-Core** | Sangat baik untuk komputasi terisolasi tanpa status (*stateless*) dan skenario keamanan defensif (*sandboxing*). | Sangat baik untuk komputasi dengan transfer data bervolume masif antar tugas (*high-throughput shared state*). |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan `waitpid()` Berulang Secara Asinkron (Non-Blocking):**
   Saat menangani `SIGCHLD`, sinyal POSIX tidak diantrekan secara berulang (*signals do not queue*). Jika tiga proses anak mati secara serentak, kernel mungkin hanya mengirimkan satu kali sinyal `SIGCHLD` ke proses induk. Oleh karena itu, *handler* harus mengeksekusi `while (waitpid(-1, &status, WNOHANG) > 0)` untuk memanen semua proses yang mati hingga antrean kosong.

2. **Jaminan Asynchronous Signal Safety:**
   Di dalam *signal handler*, jangan pernah memanggil fungsi non-reentrant seperti `printf()`, `malloc()`, atau `free()`. Pemanggilan alokasi memori di dalam signal handler saat eksekusi normal sedang berada di tengah operasi `malloc` akan memicu kondisi saling mengunci (*deadlock* pada internal heap mutex). Batasi manipulasi pada penulisan variabel bertipe `volatile sig_atomic_t` atau gunakan write non-blocking primitif `write(STDERR_FILENO, ...)`.

3. **Gunakan Flag Close-on-Exec (`FD_CLOEXEC` / `O_CLOEXEC`):**
   Secara default, deskriptor berkas yang terbuka pada parent akan diwariskan ke child setelah `fork()` dan tetap terbuka melintasi pemanggilan `execve()`. Kebocoran ini dapat memicu celah keamanan serius (child memiliki akses ke socket/file sensitif milik parent). Selalu pasang flag `FD_CLOEXEC` pada setiap file descriptor yang dibuka.

4. **Terapkan Batasan Sumber Daya (*Resource Limits*):**
   Lindungi sistem dari serangan *fork bomb* atau kehabisan memori (*out-of-memory*) menggunakan API `setrlimit()` (seperti membatasi `RLIMIT_NPROC` dan `RLIMIT_AS`) sebelum mengeksekusi kode anak yang tidak terpercaya.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Membiarkan Kemunculan Zombie Processes (*Defunct*):**
   * **Masalah:** Mengabaikan siklus pemanggilan `wait()` atau `waitpid()` pada parent yang berjalan terus-menerus (*long-running process*).
   * **Dampak:** Slot pada tabel proses kernel (*Process Table*) habis. Jika limit `pid_max` tercapai, sistem tidak dapat menjalankan perintah baru apa pun.
   * **Solusi:** Tangani `SIGCHLD` dan panen statusnya, atau abaikan secara eksplisit via `signal(SIGCHLD, SIG_IGN)` (perilaku POSIX yang secara otomatis membersihkan zombie tanpa perlu wait).

2. **Menciptakan Orphan Process Tanpa Perlindungan:**
   * **Masalah:** Parent keluar atau dibunuh lebih dulu sebelum proses anak selesai.
   * **Dampak:** Anak kehilangan parent aslinya dan diadopsi oleh proses init (PID 1) atau subreaper. Jika anak tersebut terjebak dalam *infinite loop*, ia akan memakan sumber daya sistem di latar belakang tanpa kontrol.

3. **Terjebak Deadlock Copy-On-Write Akibat Multithreading Sebelum `fork()`:**
   * **Masalah:** Memanggil `fork()` pada aplikasi yang memiliki banyak thread (*multi-threaded application*).
   * **Dampak:** Di dalam child, hanya thread pemanggil `fork()` yang diduplikasi. Jika thread lain pada parent sedang memegang kunci (*mutex*) tepat saat `fork()` dieksekusi, mutex tersebut akan berada dalam kondisi terkunci permanen di child karena pemiliknya tidak ikut diduplikasi.
   * **Solusi:** Segera panggil `execve()` sesaat setelah `fork()` di aplikasi multi-threaded, atau gunakan `pthread_atfork()` untuk membersihkan lock.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Starter): Melacak Siklus Hidup Proses Manual
* **Instruksi:** Buat sebuah program C yang melahirkan 2 proses anak. Anak pertama mencetak PID-nya, tidur selama 2 detik, lalu keluar dengan status code 10. Anak kedua tidur selama 4 detik lalu keluar dengan status code 20. Parent harus menunggu keduanya selesai secara berurutan dan mencetak durasi eksekusi serta kode keluar dari masing-masing anak.
* **Kriteria Keberhasilan:** Output menampilkan parsing nilai `WEXITSTATUS` secara tepat dari kedua anak secara non-interleaved.

### Latihan 2 (Intermediate): Mini POSIX Command Shell
* **Instruksi:** Rancang sebuah program shell interaktif mini (`minish`) yang membaca baris perintah dari terminal, mem-parsing input menjadi argumen string, melakukan `fork()`, dan mengeksekusinya via `execvp()`. Shell harus mendukung fitur eksekusi latar belakang jika perintah diakhiri dengan karakter `&` (tidak memblokir prompt shell).
* **Kriteria Keberhasilan:** Shell tidak membeku (*freeze*) ketika menjalankan perintah interaktif seperti `nano` atau perintah komputasi panjang, dan tidak meninggalkan zombie process saat perintah `&` selesai.

### Latihan 3 (Advanced): Implementasi Process Crash Sentinel via Pipes
* **Instruksi:** Rancang sistem dua-arah antara Parent (Sentinel) dan Child (Worker). Parent memonitor kesehatan child. Child mengeksekusi operasi komputasi di loop tak hingga. Komunikasikan status *heartbeat* via Anonymous Pipe non-blocking. Jika parent tidak menerima sinyal detak jantung selama lebih dari 3 detik (atau menerima error pipe broken via termination), parent harus memusnahkan child via `SIGKILL`, mencatat insiden ke file log, dan melahirkan child baru untuk melanjutkan komputasi.
* **Kriteria Keberhasilan:** Sistem mampu mendeteksi worker yang mengalami *hang* (*infinite loop* tanpa detak jantung) dan secara otomatis melakukan siklus isolasi serta regenerasi proses tanpa intervensi manual.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Instruksi mesin apa yang memicu transisi CPU dari User Mode (Ring 3) ke Kernel Mode (Ring 0) pada arsitektur x86_64 modern tanpa melalui tabel interupsi software legacy?**
   * A) `INT 0x80`
   * B) `SYSCALL`
   * C) `JMP 0x00`
   * D) `IRETQ`
   * *Jawaban yang benar: B. (Instruksi `SYSCALL` menggunakan Model Specific Registers / MSR untuk melompat langsung ke handler kernel tanpa overhead pencarian IDT).*

2. **Apa yang secara fisik terjadi pada memori RAM ketika fungsi `fork()` dieksekusi dengan mekanisme Copy-On-Write (COW)?**
   * A) Seluruh memori RAM milik parent diduplikasi secara identik ke lokasi fisik baru.
   * B) Anak hanya dialokasikan memori stack, sementara heap tetap dibagikan secara bersamaan dengan izin baca-tulis.
   * C) Kernel menduplikasi tabel halaman (page table) dan mengubah izin seluruh halaman memori parent dan child menjadi Read-Only.
   * D) Kernel tidak mengalokasikan struktur apa pun sampai fungsi `execve()` dipanggil.
   * *Jawaban yang benar: C.*

3. **Mengapa *context switch* antar-proses umumnya lebih lambat dan memakan biaya siklus CPU lebih banyak dibandingkan *context switch* antar-thread dalam proses yang sama?**
   * A) Thread tidak memerlukan stack pointer registers.
   * B) Pergantian proses mewajibkan reload direktori halaman memori (register `CR3`), yang mengakibatkan terhapusnya entri TLB dan penurunan hit-rate cache.
   * C) Proses harus selalu ditulis ke swap file sebelum proses berikutnya dieksekusi.
   * D) Thread dieksekusi langsung oleh perangkat keras tanpa intervensi kernel scheduler.
   * *Jawaban yang benar: B.*

4. **Kondisi manakah yang menyebabkan sebuah proses berstatus *Zombie* (`<defunct>`)?**
   * A) Proses induk telah mati lebih dulu daripada proses anak.
   * B) Proses kehabisan memori dan dihentikan paksa oleh Linux OOM Killer.
   * C) Proses anak telah berhenti mengeksekusi instruksi, tetapi proses induk belum memanggil `wait()` atau `waitpid()` untuk membaca status keluarnya.
   * D) Proses terjebak dalam pembacaan I/O pada disk yang rusak.
   * *Jawaban yang benar: C.*

5. **Manakah dari fungsi berikut ini yang DIJAMIN aman (*async-signal-safe*) untuk dipanggil di dalam fungsi POSIX Signal Handler?**
   * A) `printf()`
   * B) `malloc()`
   * C) `write()`
   * D) `exit()`
   * *Jawaban yang benar: C. (`write()` merupakan direct system call reentrant tanpa manipulasi internal buffer atau lock pengguna).*

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Buku Teks Wajib:**
   * Arpaci-Dusseau, R. H., & Arpaci-Dusseau, A. C. (2018). *Operating Systems: Three Easy Pieces* (OSTEP). Bab 4–6 (Processes, Process API, Direct Execution).
   * Silberschatz, A., Galvin, P. B., & Gagne, G. (2018). *Operating System Concepts* (10th ed.). Wiley. Bab 3 (Processes).
   * Love, R. (2010). *Linux Kernel Development* (3rd ed.). Addison-Wesley Professional. Bab 3: Process Management.
2. **Standard Dokumentasi & Manual Kernel:**
   * POSIX.1-2017 Standard Specification for System Interfaces (IEEE Std 1003.1).
   * Linux Programmer’s Manual: `man 2 fork`, `man 2 execve`, `man 2 waitpid`, `man 7 signal`.
3. **Kode Sumber Kernel (Linux Cross Reference):**
   * `include/linux/sched.h` (Definisi `struct task_struct`).
   * `kernel/fork.c` (Implementasi fungsi `copy_process()` dan syscall `clone`).
   * `arch/x86/entry/entry_64.S` (Mekanisme tingkat rendah penanganan instruksi `sysret`/`syscall`).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* **Proses sebagai Abstraksi Eksekusi:** Proses bukan sekadar kode program, melainkan kesatuan ruang alamat virtual mandiri, konteks register prosesor, deskriptor sumber daya, dan identitas keamanan yang dikelola oleh kernel melalui **Process Control Block (PCB)**.
* **Perlindungan Berbasis Perangkat Keras:** Dual-mode execution (User Ring 3 vs Kernel Ring 0) membatasi akses instruksi istimewa. Segala interaksi dengan hardware dijembatani oleh *system call* yang memicu transisi hak akses secara aman.
* **Mekanisme POSIX:** Pembentukan proses didasarkan pada model pemisahan tugas: `fork()` menggandakan status dengan efisiensi *Copy-On-Write*, sementara `execve()` menimpa ruang memori dengan biner baru.
* **Konkurensi & Overhead:** Ilusi multi-program diwujudkan lewat *context switching*. Meskipun memungkinkan multitasking, *context switch* antar-proses menuntut kompensasi kinerja yang signifikan akibat pemuatan ulang direktori memori dan *TLB invalidation*.
* **Manajemen yang Disiplin:** Sistem yang tangguh wajib menangani siklus hidup proses secara menyeluruh. Pengabaian terhadap sinyal asinkron dan status terminasi memicu terbentuknya *zombie process* yang dapat merusak kestabilan sistem operasi secara menyeluruh.

---

## SEKSI 17 — GLOSARIUM

* **Context Switch:** Operasi penyimpanan state prosesor dari proses yang sedang aktif dan pemulihan state proses lain yang akan dijalankan oleh CPU scheduler.
* **Copy-On-Write (COW):** Teknik optimasi manajemen memori di mana alokasi duplikasi fisik ditunda hingga salah satu proses melakukan instruksi penulisan ke halaman tersebut.
* **Orphan Process:** Proses anak yang masih aktif berjalan padahal proses induknya telah mati/selesai terlebih dahulu.
* **Process Control Block (PCB):** Struktur data internal sistem operasi yang menyimpan seluruh metadata dan status eksekusi dari suatu proses.
* **Privilege Rings:** Tingkat perlindungan hierarkis pada arsitektur prosesor untuk melindungi data dan instruksi kritis dari manipulasi program aplikasi biasa.
* **Translation Lookaside Buffer (TLB):** Cache perangkat keras pada Memory Management Unit (MMU) yang menyimpan translasi alamat virtual ke alamat fisik untuk mempercepat akses memori.
* **Zombie Process:** Proses yang telah menghentikan eksekusinya, tetapi entrinya dalam tabel proses kernel masih dipertahankan hingga parent membaca status keluarnya.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Metodologi Pengajaran:**
  * Mulailah sesi lab dengan memerintahkan mahasiswa membuka dua terminal: satu untuk menjalankan skrip C yang memicu fork tak berujung secara terkendali, dan satu lagi menjalankan `top`, `htop`, atau `ps -efl` untuk mengamati status `Z` (Zombie) secara langsung.
  * Hindari mengaburkan konsep antara *Program*, *Proses*, dan *Thread*. Tegaskan batas kepemilikan memori fisik dan virtual sebelum masuk ke latihan koding.
* **Hambatan Konseptual yang Sering Terjadi:**
  * Banyak peserta didik kebingungan mengapa `fork()` menghasilkan dua nilai kembalian yang berbeda secara bersamaan. Gambarkan visualisasi percabangan instruksi CPU sejak instruksi `int 0x80`/`syscall` kembali (*returns*).
  * Peserta sering berasumsi bahwa memory copy pada `fork()` langsung memakan RAM dua kali lipat. Tunjukkan mekanisme *Copy-On-Write* dengan membaca perubahan metrik memori pada `/proc/[pid]/smaps`.
* **Kebutuhan Lingkungan Lab:**
  * Kompilator GCC/Clang dengan flag `-Wall -Wextra -pedantic -std=c99` (atau c11).
  * Lingkungan Linux asli (Ubuntu 22.04 LTS / Debian 12) atau WSL2. Jangan gunakan macOS untuk praktikum sinyal tingkat rendah karena perbedaan semantik POSIX/BSD pada beberapa penanganan default sinyal.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Februari 2025):**
  * Rilis versi awal kurikulum teknik fondasi sistem operasi.
  * Standarisasi arsitektur modul mengacu pada format 20 seksi GEMINI.md.
  * Penambahan implementasi Supervisor Pattern berbasis async-signal-safe dan evaluasi mendalam mekanisme register x86_64 context-switch.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `CS-CF-02-03: Arsitektur Memori Hirarkis, Cache & Bus Komputer`
* **Modul Saat Ini:** `CS-CF-03-01: Sistem Operasi & Manajemen Proses`
* **Modul Berikutnya:** `CS-CF-03-02: Threading, Konkurensi & Primitif Sinkronisasi Mutex/Semaphore`