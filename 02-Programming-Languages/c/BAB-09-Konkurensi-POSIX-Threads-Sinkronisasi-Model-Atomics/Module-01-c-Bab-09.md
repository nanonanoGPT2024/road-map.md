# SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** `02-Programming-Languages`
* **Track:** Bahasa Pemrograman C Tingkat Mahir (Advanced C Systems Programming)
* **Bab:** 09 — Pemrograman Konkuren & Sistem Terdistribusi Rendah
* **Modul:** 01 — Konkurensi POSIX Threads, Sinkronisasi, & Model Atomics
* **Standar Spesifikasi:** POSIX.1-2008 (`IEEE Std 1003.1-2008`), ISO/IEC 9899:2011 (C11), GNU/Linux NPTL (*Native POSIX Thread Library*)
* **Prasyarat Pengetahuan:** Alokasi Memori Dinamis C (`malloc`/`free`), Penanganan *Pointers* Tingkat Lanjut, Manajemen Memori Tingkat Rendah (*Stack* vs *Heap*), dan Konsep Dasar Sistem Operasi (*Context Switch*, *Virtual Memory*, *Kernel vs User Space*).

---

# SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik memiliki kapabilitas komprehensif untuk:

1. **Menerapkan Primitif POSIX Threads:** Merancang siklus hidup *thread* (pembuatan, terminasi, kanalisasi argumen, dan sinkronisasi terminasi) menggunakan `pthread_create`, `pthread_join`, `pthread_detach`, serta mengelola atribut *thread* melalui `pthread_attr_t`.
2. **Menguasai Mekanisme Sinkronisasi Klasik:** Memilih dan mengimplementasikan primitif sinkronisasi kernel/pengguna (`pthread_mutex_t`, `pthread_cond_t`, `pthread_rwlock_t`) secara tepat guna mengeliminasi kondisi balapan (*race condition*) dan mencegah kondisi kebuntuan (*deadlock*).
3. **Menganalisis Spurious Wakeups:** Memahami rasional arsitektural di balik *spurious wakeup* pada *condition variables* dan mengonstruksi *synchronization loops* yang tahan uji (*resilient*).
4. **Menerapkan Model C11 Atomics:** Memanfaatkan pustaka `<stdatomic.h>` untuk mengeksekusi operasi bebas kunci (*lock-free*) dan memetakan operasi memori atomik ke instruksi mesin (*hardware primitives* seperti x86 `LOCK CMPXCHG` atau ARM `LDREX/STREX`).
5. **Menavigasi Hardware Memory Ordering:** Membedakan karakteristik eksekusi *Relaxed*, *Acquire-Release*, dan *Sequentially Consistent* (`memory_order_seq_cst`) untuk merancang struktur data berkecepatan tinggi tanpa memicu anomali *memory reordering* akibat optimasi compiler atau mikroarsitektur CPU.
6. **Mendeteksi dan Memitigasi Masalah Kinerja Mikro:** Mengidentifikasi dan menyelesaikan fenomena *false sharing* melalui pelurusan memori (*cache-line alignment*), serta melakukan *debugging data races* menggunakan *tooling* modern (ThreadSanitizer dan GDB).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model Eksekusi Konkuren
Dalam model eksekusi sekuensial, CPU membaca instruksi secara deterministik dari atas ke bawah. Namun, dalam sistem multi-inti (*multi-core*), memori sistem bukan lagi jalur data tunggal, melainkan sebuah **sistem terdistribusi mikro**. 

Anggap setiap *CPU Core* sebagai seorang pekerja independen yang memiliki catatan pribadi super cepat (*L1/L2 Caches*, *Store Buffers*), dan RAM fisik sebagai buku besar sentral yang lambat. Ketika dua *thread* memodifikasi variabel yang sama tanpa koordinasi:
- Operasi tulis tidak langsung diteruskan ke RAM.
- CPU dapat mengubah urutan instruksi (*Out-of-Order Execution*) demi efisiensi pipa instruksi (*pipeline*).
- Compiler C dapat membuang, menata ulang, atau menyimpan variabel di dalam register CPU secara permanen (*Compiler Reordering*).

```
   +-----------------------------------------------------------+
   |                SHARED PHYSICAL MEMORY (RAM)               |
   +-----------------------------------------------------------+
                     ^                       ^
     Cache Flush /   |                       | Cache Flush /
     Invalidation    v                       v Invalidation
   +----------------------+             +----------------------+
   |     CPU CORE 0       |             |      CPU CORE 1      |
   | +------------------+ |             | +------------------+ |
   | | L1/L2 Cache      | |             | | L1/L2 Cache      | |
   | +------------------+ |             | +------------------+ |
   | | Store Buffer     | |             | | Store Buffer     | |
   | +------------------+ |             | +------------------+ |
   | | Execution Engine | |             | | Execution Engine | |
   | +------------------+ |             | +------------------+ |
   | Thread A Execution   |             | Thread B Execution   |
   +----------------------+             +----------------------+
```

### Paradigma: Sinkronisasi Bukan Sekadar "Kunci Pintu"
Sinkronisasi bukan hanya tentang mencegah dua *thread* berada di blok kode yang sama pada saat bersamaan (*Mutual Exclusion*). Sinkronisasi adalah tentang **visibilitas memori** (*Memory Visibility*) dan **pemesanan instruksi** (*Memory Ordering*). Mutex atau operasi atomik bertindak sebagai dinding pembatas (*Memory Barrier / Fence*) yang memaksa perangkat keras dan compiler meratakan status memori antar cache CPU.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Arsitektur POSIX Threads vs Ruang Memori Proses
Setiap *thread* dalam sebuah proses POSIX memiliki *stack* eksekusi mandiri, salinan register CPU, serta topeng sinyal (*signal mask*). Namun, mereka berbagi ruang alamat virtual yang sama: *Text segment* (kode program), *Data/BSS segment* (variabel global/statis), *Heap* (alokasi dinamis), dan deskriptor berkas (*file descriptors*).

```
+------------------------------------------------------------------+
|                     VIRTUAL ADDRESS SPACE                        |
|                                                                  |
|  +------------------------------------------------------------+  |
|  | Text Segment (Binary Instructions, Shared Read-Only)       |  |
|  +------------------------------------------------------------+  |
|  | Data & BSS Segments (Global & Static Variables, Shared)    |  |
|  +------------------------------------------------------------+  |
|  | Heap (Dynamically Allocated Memory: malloc/free, Shared)   |  |
|  +------------------------------------------------------------+  |
|  |                              v                             |  |
|  |                              ^                             |  |
|  |  +-----------------------+      +-----------------------+  |  |
|  |  | Thread 1 Stack        |      | Thread 2 Stack        |  |  |
|  |  | (Local Vars, Frames)  |      | (Local Vars, Frames)  |  |  |
|  |  +-----------------------+      +-----------------------+  |  |
|  |  | Thread 1 Registers    |      | Thread 2 Registers    |  |  |
|  |  | (Program Counter, SP) |      | (Program Counter, SP) |  |  |
|  +--+-----------------------+------+-----------------------+--+  |
|  | Shared Open File Descriptors, Sockets, and Signal Handlers |  |
+--+------------------------------------------------------------+--+
```

### Siklus Hidup Pthread: Alur Eksekusi & Sinkronisasi

```
   MAIN THREAD                         WORKER THREAD
        |
        | pthread_create(&tid, NULL, worker_func, arg)
        |----------------------------------------+
        |                                        |
        | [Main thread continues or waits]      | [Worker starts execution]
        |                                        | worker_func(arg)
        |                                        |   - Allocates local stack
        |                                        |   - Performs computation
        | pthread_join(tid, &res)                |
        |   - Suspends execution                 |
        |   - Waits for worker completion        |
        |     .                                  | return (void*)result;
        |     .                                  |   OR pthread_exit(res);
        |     . <--------------------------------+
        | [Wakes up, reaps worker resources]
        | [res receives pointer from worker]
        v
   Exit Application
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. POSIX Threads Implementation: NPTL & `clone(2)`
Pada sistem Linux modern, POSIX Threads diimplementasikan melalui **NPTL** (*Native POSIX Thread Library*). Sebuah *thread* sejatinya adalah proses berbobot ringan (*lightweight process* / LWP) yang dibuat menggunakan pemanggilan sistem (*system call*) fundamental: `clone(2)`.

Flag kritis yang digunakan oleh NPTL saat memanggil `clone`:
* `CLONE_VM`: Membagi ruang alamat memori virtual yang sama.
* `CLONE_FS`: Membagi informasi sistem berkas yang sama (*root*, *cwd*).
* `CLONE_FILES`: Membagi tabel deskriptor berkas (*open file table*).
* `CLONE_SIGHAND`: Membagi tabel pengendali sinyal (*signal handlers*).
* `CLONE_THREAD`: Menempatkan proses anak ke dalam *thread group* yang sama dengan proses pemanggil (sehingga memiliki PID proses yang sama).

### 2. Anatomi Internal `pthread_mutex_t` dan Mekanisme Futex
Sebuah implementasi *naive* (primitif) dari mutex akan memanggil kernel setiap kali fungsi `lock()` atau `unlock()` dijalankan. Ini sangat lambat karena adanya biaya *context switch* ruang pengguna (*user space*) ke ruang kernel (*kernel space*). 

Pthread pada Linux menggunakan **Futex** (*Fast Userspace Mutex*):
1. **Kasus Cepat (Uncontended Path):** Menggunakan instruksi atomik CPU (seperti `atomic_compare_exchange` / `LOCK CMPXCHG`). Jika mutex bebas, *thread* langsung memperoleh hak akses secara murni di *user space* tanpa *system call*. Biaya eksekusi hanya beberapa siklus CPU (nanodetik).
2. **Kasus Lambat (Contended Path):** Jika mutex telah dikunci oleh *thread* lain, *thread* pemanggil melakukan eskalasi dengan mengeksekusi *system call* `sys_futex(FUTEX_WAIT, ...)`. Kernel menempatkan *thread* ke dalam antrean tunggu (*sleep state*) hingga pemilik mutex memanggil `pthread_mutex_unlock()`, yang kemudian memicu `sys_futex(FUTEX_WAKE, ...)`.

### 3. Hardware Cache Coherency (MESI Protocol)
Pada tingkat perangkat keras, prosesor mempertahankan konsistensi data antar-cache inti CPU menggunakan protokol seperti **MESI** (*Modified, Exclusive, Shared, Invalid*):
* **Modified (M):** Baris cache (*cache line*, biasanya 64 byte) hanya ada pada core ini dan statusnya kotor (*dirty* - berbeda dari memori utama).
* **Exclusive (E):** Data sama dengan RAM, hanya ada di satu core.
* **Shared (S):** Data bersih, ada di beberapa core secara bersamaan (hanya boleh dibaca).
* **Invalid (I):** Data tidak lagi valid karena core lain telah menulis ke alamat memori dalam *cache line* tersebut.

Ketika Core A menulis data ke alamat variabel, pesan pembatalan (*invalidation queue*) disiarkan ke Core B. Core B harus menandai baris cache-nya sebagai *Invalid*. Inilah alasan mengapa komunikasi antar-thread melalui variabel biasa tanpa primitif sinkronisasi menghasilkan pembacaan data basi (*stale data*).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Kondisi Balapan (Race Conditions) & Segmen Kritis
*Race condition* terjadi ketika dua atau lebih operasi konkuren mengakses sumber daya bersama tanpa sinkronisasi yang memadai, dan minimal salah satu dari operasi tersebut adalah penulisan (*write*). Urutan penyelesaian instruksi menjadi nondeterministik tergantung pada penjadwal OS (*OS Scheduler*). Bagian kode yang mengakses memori bersama ini disebut **Critical Section**.

### Spurious Wakeups pada Condition Variables
Fungsi `pthread_cond_wait()` digunakan untuk menghentikan sementara eksekusi *thread* hingga sebuah kondisi bernilai benar. Namun, standar POSIX secara eksplisit mengizinkan terjadinya **Spurious Wakeup** (kebangkitan palsu): *thread* dapat terbangun dari status tidurnya meskipun tidak ada *signal* atau *broadcast* yang dikirimkan.

**Mengapa ini diizinkan oleh standar arsitektur?**
Pada sistem multiprosesor/multicore, menangani sinyal kernel secara atomik sempurna tanpa membangkitkan *thread* yang salah akan membutuhkan *overhead* perangkat lunak dan perangkat keras yang sangat mahal pada layer kernel. Mengizinkan *spurious wakeup* memungkinkan kernel dan layer pustaka thread mengimplementasikan primitif bangun tidur secara sangat cepat dan efisien.

Implikasi Desain Wajib: Pengecekan predikat kondisi **HARUS SELALU** dibungkus dalam sebuah *loop* (`while`), **TIDAK PERNAH** menggunakan percabangan sederhana (`if`).

```c
/* SALAH: Rentan terhadap spurious wakeups */
if (!data_is_ready) {
    pthread_cond_wait(&cv, &mutex);
}

/* BENAR: Evaluasi ulang kondisi setelah terbangun */
while (!data_is_ready) {
    pthread_cond_wait(&cv, &mutex);
}
```

### Model Memori C11 (ISO/IEC 9899:2011) & Atomics
Standar C11 memperkenalkan model memori formal ke dalam bahasa C. Sebelumnya, C tidak memiliki konsep *thread* formal pada tingkat bahasa (bergantung sepenuhnya pada pustaka eksternal seperti pthreads).

#### 1. Operasi Atomik vs Non-Atomik
Operasi seperti `i++` pada tipe data primitif `int` **bukanlah** operasi atomik. Operasi ini terdiri dari tiga langkah instruksi CPU:
1. `READ`: Muat nilai memori `i` ke register CPU.
2. `MODIFY`: Tambahkan 1 ke register CPU.
3. `WRITE`: Tuliskan kembali nilai register ke alamat memori `i`.

Jika dua thread mengeksekusi `i++` bersamaan, langkah-langkah ini dapat saling silang (*interleaved*), memicu kehilangan pembaruan data (*lost update*). Variabel `atomic_int` menjamin ketiga langkah di atas dieksekusi secara tak terpisahkan (*indivisible*).

#### 2. Spektrum Memory Ordering pada C11
C11 mendefinisikan kontrol granularitas terhadap bagaimana instruksi memori dapat diurutkan ulang (*reordered*):

1. **`memory_order_relaxed`:**
   * Menjamin atomisitas operasi, tetapi **TIDAK ADA** jaminan sinkronisasi urutan instruksi di sekitar operasi tersebut.
   * Sangat cepat; digunakan untuk penghitung (*counters*) sederhana yang tidak mengontrol alur data lain.

2. **`memory_order_release` & `memory_order_acquire` (Acquire-Release Semantics):**
   * **Acquire (Load):** Menjamin bahwa tidak ada operasi baca atau tulis dalam program yang dapat dipindahkan oleh compiler/CPU ke posisi *sebelum* instruksi acquire ini.
   * **Release (Store):** Menjamin bahwa semua operasi baca atau tulis sebelum instruksi ini dijamin sudah selesai dan dipublikasikan *sebelum* status release ditulis ke memori.
   * Digunakan untuk membangun mekanisme koordinasi kunci (*lockless synchronization*).

3. **`memory_order_seq_cst` (Sequentially Consistent):**
   * Model default dan terketat. Menjamin adanya urutan eksekusi global yang identik yang diamati oleh semua *core* CPU.
   * Menghasilkan *memory fence/barrier* perangkat keras secara penuh (misalnya instruksi `MFENCE` pada x86). Memiliki dampak performa terbesar.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah program mandiri yang mendemonstrasikan:
1. Pembuatan dan penggabungan POSIX Threads.
2. Pencegahan *data race* pada variabel akumulator menggunakan `pthread_mutex_t`.
3. Pemanfaatan `stdatomic.h` untuk perbandingan performa/mekanisme.

Program ditulis dalam standar C11 dan POSIX.1-2008.

Simpan kode ini dengan nama `fundamental_concurrency.c`:

```c
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <pthread.h>
#include <stdatomic.h>
#include <errno.h>

#define NUM_THREADS 4
#define INCREMENTS_PER_THREAD 1000000

typedef struct {
    long long unsafe_counter;
    long long mutex_counter;
    pthread_mutex_t lock;
    atomic_llong atomic_counter;
} SharedData;

typedef struct {
    int thread_id;
    SharedData *shared;
} WorkerContext;

static void* worker_routine(void *arg) {
    WorkerContext *ctx = (WorkerContext *)arg;
    SharedData *data = ctx->shared;

    for (int i = 0; i < INCREMENTS_PER_THREAD; ++i) {
        // 1. UNSAFE: Data Race yang disengaja untuk demonstrasi
        data->unsafe_counter++;

        // 2. MUTEX: Sinkronisasi Tradisional via Locking
        int rc = pthread_mutex_lock(&data->lock);
        if (rc != 0) {
            fprintf(stderr, "Fatal error on pthread_mutex_lock: %d\n", rc);
            abort();
        }
        data->mutex_counter++;
        pthread_mutex_unlock(&data->lock);

        // 3. ATOMIC: Sinkronisasi Lock-free C11 (Relaxed Ordering)
        atomic_fetch_add_explicit(&data->atomic_counter, 1, memory_order_relaxed);
    }

    return NULL;
}

int main(void) {
    pthread_t threads[NUM_THREADS];
    WorkerContext contexts[NUM_THREADS];
    SharedData shared = {
        .unsafe_counter = 0,
        .mutex_counter = 0,
        .atomic_counter = ATOMIC_VAR_INIT(0)
    };

    if (pthread_mutex_init(&shared.lock, NULL) != 0) {
        perror("Gagal menginisialisasi mutex");
        return EXIT_FAILURE;
    }

    printf("Memulai %d threads, masing-masing melakukan %d increment...\n", 
           NUM_THREADS, INCREMENTS_PER_THREAD);

    for (int i = 0; i < NUM_THREADS; ++i) {
        contexts[i].thread_id = i;
        contexts[i].shared = &shared;

        int rc = pthread_create(&threads[i], NULL, worker_routine, &contexts[i]);
        if (rc != 0) {
            fprintf(stderr, "Gagal membuat thread %d: kode error %d\n", i, rc);
            return EXIT_FAILURE;
        }
    }

    for (int i = 0; i < NUM_THREADS; ++i) {
        int rc = pthread_join(threads[i], NULL);
        if (rc != 0) {
            fprintf(stderr, "Gagal join thread %d: kode error %d\n", i, rc);
            return EXIT_FAILURE;
        }
    }

    pthread_mutex_destroy(&shared.lock);

    long long expected_total = (long long)NUM_THREADS * INCREMENTS_PER_THREAD;
    printf("\n=== HASIL EKSEKUSI ===\n");
    printf("Expected Target : %lld\n", expected_total);
    printf("Unsafe Counter  : %lld (Kemungkinan corrupt/loss updates)\n", shared.unsafe_counter);
    printf("Mutex Counter   : %lld (Valid)\n", shared.mutex_counter);
    printf("Atomic Counter  : %lld (Valid)\n", (long long)shared.atomic_counter);

    return EXIT_SUCCESS;
}
```

### Instruksi Kompilasi & Eksekusi

```bash
# Kompilasi dengan C11 dan dukungan POSIX Threads
gcc -std=c11 -Wall -Wextra -pthread fundamental_concurrency.c -o fundamental_concurrency

# Eksekusi
./fundamental_concurrency
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis komponen vital dari `fundamental_concurrency.c`:

1. **Baris 1:** `#define _POSIX_C_SOURCE 200809L`
   * *Makna Teknis:* Memberitahu compiler C runtime (`glibc`) untuk mengekspos fungsi, konstanta, dan tipe data yang sesuai dengan standar POSIX.1-2008. Tanpa macro ini, beberapa definisi pustaka thread dan waktu mungkin tidak diimpor dengan sempurna saat kompilasi dengan opsi ketat `-std=c11`.

2. **Baris 11-16:** Definisi `SharedData`
   * Mengelompokkan semua variabel yang berstatus *shared-state* ke dalam satu representasi memori. `pthread_mutex_t` dideklarasikan berdampingan dengan data yang dilindunginya untuk merepresentasikan hubungan kepemilikan data (*data encapsulation*).

3. **Baris 14:** `atomic_llong atomic_counter;`
   * Menggunakan tipe atomik standar ISO C11 untuk variabel `long long`. Tipe ini menjamin bahwa seluruh operasi pembacaan, penulisan, dan modifikasi terhadap variabel ini dipetakan ke instruksi atomik perangkat keras yang tidak dapat diinterupsi oleh peralihan thread.

4. **Baris 29:** `data->unsafe_counter++;`
   * *Critical Section Bug:* Operasi non-atomik. Pada arsitektur x86_64, ini diuraikan menjadi instruksi `mov`, `add`, dan `mov` kembali ke RAM. Ketika context switch terjadi di antara instruksi-instruksi tersebut, nilai yang ditulis oleh thread lain akan tertimpa dan hilang.

5. **Baris 32-37:** Siklus Penguncian Mutex
   * `pthread_mutex_lock(&data->lock)`: Memeriksa ketersediaan lock. Jika lock sedang dipegang thread lain, thread masuk ke antrean kernel (Futex wait).
   * Nilai balik diperiksa secara ketat (`rc != 0`). Kesalahan penanganan mutex merupakan kesalahan sistem fatal.
   * `pthread_mutex_unlock(&data->lock)`: Melepaskan lock dan membangkitkan salah satu thread yang sedang tidur menunggu mutex.

6. **Baris 40:** `atomic_fetch_add_explicit(&data->atomic_counter, 1, memory_order_relaxed);`
   * Mengeksekusi penambahan nilai atomik tanpa *overhead* mutex.
   * `memory_order_relaxed` digunakan karena counter ini hanya berfungsi sebagai akumulator independen; kita tidak menggunakannya untuk memvalidasi ketersediaan data pada variabel lain, sehingga kita tidak memerlukan *memory synchronization barrier* yang membebani CPU pipeline.

7. **Baris 58:** `pthread_create(&threads[i], NULL, worker_routine, &contexts[i]);`
   * Menginstruksikan kernel untuk mengalokasikan stack baru dan mendaftarkan LWP baru. Parameter keempat meneruskan pointer ke struktur konteks independen `contexts[i]`. **Penting:** Kita mem-pass alamat elemen array yang independen, bukan variabel iterator loop `&i` yang akan memicu *data race* pada ID thread.

8. **Baris 67:** `pthread_join(threads[i], NULL);`
   * Menahan eksekusi `main` thread hingga target thread menyelesaikan fungsi eksekusinya. Fungsi ini membebaskan sumber daya kernel yang dialokasikan untuk thread tersebut (mencegah *thread leakage* / *zombie thread*).

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Masalah: High-Throughput Thread-Safe Bounded Message Queue
Pada sistem telemetri jaringan berkecepatan tinggi, paket data mentah masuk dari thread penerima socket IO (*Producer*) dan harus didistribusikan ke sekumpulan thread analitik data (*Consumers*). 

**Kebutuhan Sistem:**
1. Antrean harus memiliki batas kapasitas memori maksimum (*bounded capacity*) untuk mencegah kehabisan RAM (*Out-Of-Memory*) jika produsen lebih cepat dari konsumen (*backpressure handling*).
2. Jika antrean penuh, *Producer* harus tidur (*block*) hingga ruang tersedia.
3. Jika antrean kosong, *Consumer* harus tidur (*block*) hingga item baru masuk.
4. Mekanisme harus sepenuhnya *thread-safe* di lingkungan *Multi-Producer Multi-Consumer* (MPMC).
5. Sistem harus mendukung mekanisme *Graceful Shutdown* di mana semua thread dapat berhenti secara bersih tanpa kehilangan memori (*memory leak*).

**Solusi Arsitektur:**
Menggunakan struktur data *Circular Ring Buffer* yang dilindungi oleh sebuah `pthread_mutex_t` dan dua buah `pthread_cond_t` (`not_empty` dan `not_full`), ditambah satu flag atomik untuk propagasi sinyal terminasi program.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem produksi *Thread-Safe Bounded Queue* (MPMC) yang lengkap, tangguh, dan bebas dari kebocoran memori.

Simpan sebagai `bounded_mpmc_queue.c`:

```c
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <pthread.h>
#include <stdatomic.h>
#include <unistd.h>
#include <errno.h>

typedef struct {
    void **buffer;
    size_t capacity;
    size_t head;
    size_t tail;
    size_t count;
    bool shutdown;
    pthread_mutex_t lock;
    pthread_cond_t not_empty;
    pthread_cond_t not_full;
} BoundedQueue;

typedef struct {
    int id;
    int payload_value;
} Message;

// Inisialisasi Queue
BoundedQueue* queue_create(size_t capacity) {
    if (capacity == 0) return NULL;

    BoundedQueue *q = malloc(sizeof(BoundedQueue));
    if (!q) return NULL;

    q->buffer = malloc(sizeof(void*) * capacity);
    if (!q->buffer) {
        free(q);
        return NULL;
    }

    q->capacity = capacity;
    q->head = 0;
    q->tail = 0;
    q->count = 0;
    q->shutdown = false;

    pthread_mutex_init(&q->lock, NULL);
    pthread_cond_init(&q->not_empty, NULL);
    pthread_cond_init(&q->not_full, NULL);

    return q;
}

// Push item (Producer)
bool queue_push(BoundedQueue *q, void *item) {
    pthread_mutex_lock(&q->lock);

    // Evaluasi loop untuk menangani spurious wakeup dan kapasitas
    while (q->count == q->capacity && !q->shutdown) {
        pthread_cond_wait(&q->not_full, &q->lock);
    }

    if (q->shutdown) {
        pthread_mutex_unlock(&q->lock);
        return false;
    }

    q->buffer[q->tail] = item;
    q->tail = (q->tail + 1) % q->capacity;
    q->count++;

    // Beritahukan konsumen bahwa data tersedia
    pthread_cond_signal(&q->not_empty);

    pthread_mutex_unlock(&q->lock);
    return true;
}

// Pop item (Consumer)
bool queue_pop(BoundedQueue *q, void **item) {
    pthread_mutex_lock(&q->lock);

    while (q->count == 0 && !q->shutdown) {
        pthread_cond_wait(&q->not_empty, &q->lock);
    }

    if (q->count == 0 && q->shutdown) {
        pthread_mutex_unlock(&q->lock);
        return false;
    }

    *item = q->buffer[q->head];
    q->head = (q->head + 1) % q->capacity;
    q->count--;

    // Beritahukan produsen bahwa slot telah kosong
    pthread_cond_signal(&q->not_full);

    pthread_mutex_unlock(&q->lock);
    return true;
}

// Menghentikan Queue dan membangunkan semua thread
void queue_shutdown(BoundedQueue *q) {
    pthread_mutex_lock(&q->lock);
    q->shutdown = true;
    pthread_cond_broadcast(&q->not_empty);
    pthread_cond_broadcast(&q->not_full);
    pthread_mutex_unlock(&q->lock);
}

// Dealokasi Queue
void queue_destroy(BoundedQueue *q) {
    if (!q) return;
    pthread_mutex_destroy(&q->lock);
    pthread_cond_destroy(&q->not_empty);
    pthread_cond_destroy(&q->not_full);
    free(q->buffer);
    free(q);
}

/* ================= SIMULASI MULTI-THREADING ================= */

#define NUM_PRODUCERS 2
#define NUM_CONSUMERS 4
#define ITEMS_PER_PRODUCER 20

static atomic_int g_items_produced = ATOMIC_VAR_INIT(0);
static atomic_int g_items_consumed = ATOMIC_VAR_INIT(0);

void* producer_worker(void *arg) {
    BoundedQueue *q = (BoundedQueue*)arg;
    
    for (int i = 0; i < ITEMS_PER_PRODUCER; ++i) {
        Message *msg = malloc(sizeof(Message));
        msg->id = atomic_fetch_add(&g_items_produced, 1);
        msg->payload_value = rand() % 1000;

        if (!queue_push(q, msg)) {
            // Jika shutdown dipanggil sebelum selesai
            free(msg);
            break;
        }
        usleep(10000); // Simulasi kerja I/O 10ms
    }
    return NULL;
}

void* consumer_worker(void *arg) {
    BoundedQueue *q = (BoundedQueue*)arg;
    void *raw_item = NULL;

    while (queue_pop(q, &raw_item)) {
        Message *msg = (Message*)raw_item;
        atomic_fetch_add(&g_items_consumed, 1);
        printf("[Consumer %lu] Memproses Pesan ID: %02d (Val: %d)\n", 
               (unsigned long)pthread_self(), msg->id, msg->payload_value);
        free(msg);
        usleep(25000); // Simulasi pemrosesan 25ms
    }
    return NULL;
}

int main(void) {
    srand(42);
    BoundedQueue *q = queue_create(5); // Kapasitas kecil untuk memaksa blocking

    pthread_t producers[NUM_PRODUCERS];
    pthread_t consumers[NUM_CONSUMERS];

    printf("Menginisialisasi sistem: %d Produsen, %d Konsumen, Kapasitas Antrean: 5\n\n",
           NUM_PRODUCERS, NUM_CONSUMERS);

    for (int i = 0; i < NUM_CONSUMERS; ++i) {
        pthread_create(&consumers[i], NULL, consumer_worker, q);
    }
    for (int i = 0; i < NUM_PRODUCERS; ++i) {
        pthread_create(&producers[i], NULL, producer_worker, q);
    }

    // Tunggu semua produsen selesai memproduksi pesan
    for (int i = 0; i < NUM_PRODUCERS; ++i) {
        pthread_join(producers[i], NULL);
    }
    printf("\n--> Semua produsen selesai. Mematikan sistem antrean...\n");

    // Lakukan graceful shutdown dan tunggu antrean terkuras
    queue_shutdown(q);

    // Tunggu semua konsumen memproses sisa data dan berhenti
    for (int i = 0; i < NUM_CONSUMERS; ++i) {
        pthread_join(consumers[i], NULL);
    }

    printf("\n=== STATISTIK EKSEKUSI ===\n");
    printf("Total Item Diproduksi: %d\n", atomic_load(&g_items_produced));
    printf("Total Item Dikonsumsi: %d\n", atomic_load(&g_items_consumed));

    queue_destroy(q);
    printf("Semua sumber daya memori dan primitif POSIX berhasil dibebaskan.\n");

    return EXIT_SUCCESS;
}
```

### Panduan Verifikasi & Eksekusi

```bash
# Kompilasi kode dengan AddressSanitizer & UndefinedBehaviorSanitizer
gcc -std=c11 -Wall -Wextra -pthread -fsanitize=address,undefined bounded_mpmc_queue.c -o bounded_mpmc_queue

# Jalankan program
./bounded_mpmc_queue
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih mekanisme sinkronisasi yang tepat menuntut pemahaman mendalam atas kompromi antara kemudahan abstraksi, latensi, pemanfaatan daya, dan *throughput*.

| Parameter Evaluasi | Mutex Tradisional (`pthread_mutex_t`) | Read-Write Lock (`pthread_rwlock_t`) | C11 Atomics / Lock-Free |
| :--- | :--- | :--- | :--- |
| **Beban Kompleksitas Kode** | Rendah (Paling intuitif dan aman) | Menengah (Harus hati-hati membedakan reader vs writer) | Sangat Tinggi (Rentan terhadap bugs ABA, memory ordering) |
| **Overhead CPU (Uncontended)** | Rendah (~10-25 ns via Futex fast-path) | Menengah (~30-50 ns karena status pembaca ganda) | Hampir Nol (~1-5 ns, instruksi native hardware) |
| **Perilaku Saat Contended** | Menghentikan eksekusi thread (*Sleep* via OS scheduler), hemat energi baterai/CPU. | Menghentikan eksekusi thread jika terdapat *Writer active*. | Spinlock / CAS loop mengonsumsi siklus CPU 100% (*burns CPU*). |
| **Kasus Penggunaan Optimal** | Modifikasi struktur data yang kompleks, komputasi *critical section* yang panjang. | Sistem dengan rasio *Read-Heavy* tinggi (>90% baca, <10% tulis), misal routing table. | Variabel flag sederhana, State Machines mikro, counters berkecepatan tinggi. |
| **Risiko Masalah Klasik** | *Deadlock*, *Priority Inversion*. | *Writer Starvation* (jika pembaca terus berdatangan). | *ABA Problem*, *Memory Misordering*, *Live-lock*. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The ABA Problem pada Lock-Free Primitives
Kondisi ini terjadi ketika operasi *Compare-And-Swap* (CAS) membaca lokasi memori $A$, melihat nilainya masih $A$, lalu berasumsi bahwa tidak ada perubahan yang terjadi pada struktur data, padahal nilainya sempat diubah ke $B$ dan dikembalikan ke $A$.
* *Dampak Nyata:* Pada antrean *lock-free stack*, ini menyebabkan penunjuk pointer dangling merujuk ke memori yang telah di-*free*, mengakibatkan korupsi memori fatal (*Segmentation Fault*).
* *Solusi:* Gunakan *Tagged Pointers* (menyimpan counter versi di samping pointer menggunakan atomic 128-bit) atau gunakan pustaka hazard pointers / RCU (*Read-Copy Update*).

### 2. Spurious Wakeups
Telah dianalisis pada Seksi 06. Jika Anda menggunakan konstruksi:
```c
if (queue->count == 0) {
    pthread_cond_wait(&cv, &mutex);
}
// Eksekusi pop data di sini...
```
Thread berisiko bangun saat antrean masih kosong karena adanya *interrupted system call* pada kernel Linux. Akses terhadap buffer kosong akan memicu *out-of-bounds read* atau *null pointer dereference*.

### 3. Mutex Destruction Undefined Behavior
Menghancurkan mutex yang sedang terkunci atau sedang ditunggu oleh *thread* lain menggunakan `pthread_mutex_destroy()` menghasilkan *Undefined Behavior* (UB). Pada glibc, ini sering kali tidak langsung crash, melainkan merusak struktur data futex kernel secara senyap hingga menyebabkan aplikasi hang di kemudian hari.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Passing Pointer Variabel Lokal Loop ke `pthread_create`
```c
// KESALAHAN FATAL:
for (int i = 0; i < 5; ++i) {
    pthread_create(&tids[i], NULL, worker, (void*)&i); // Meneruskan alamat lokal 'i'
}
```
*Mengapa Salah?* Variabel `i` dialokasikan pada stack pemanggil. Karena loop berjalan lebih cepat daripada kernel menjadwalkan thread, banyak thread akan membaca nilai `i` yang sama setelah terinkrementasi, atau bahkan membaca alamat stack yang telah hangus saat fungsi pemanggil keluar (*Dangling Pointer*).
*Solusi:* Alokasikan array struktur konteks per-thread, atau salin nilai integer ke heap, atau konversi langsung ke `intptr_t` jika tipe data muat dalam pointer:
```c
pthread_create(&tids[i], NULL, worker, (void*)(intptr_t)i);
```

### Kesalahan 2: Deadlock Akibat Lock Ordering Inversion
Thread 1 mengunci Mutex A lalu mencoba mengunci Mutex B. Pada saat bersamaan, Thread 2 mengunci Mutex B lalu mencoba mengunci Mutex A. Keduanya saling menunggu selamanya.

```
Thread 1: Lock(A) ---> Mencoba Lock(B) [TERKUNCI OLEH THREAD 2]
Thread 2: Lock(B) ---> Mencoba Lock(A) [TERKUNCI OLEH THREAD 1]
```
*Solusi:* **Terapkan Hierarki Kunci Global.** Seluruh tim rekayasa perangkat lunak harus mendefinisikan aturan ketat: Kunci harus selalu diakuisisi dengan urutan leksikografis/alamat memori yang tetap (contoh: selalu peroleh pointer terkecil terlebih dahulu):
```c
void lock_both(pthread_mutex_t *m1, pthread_mutex_t *m2) {
    if (m1 < m2) {
        pthread_mutex_lock(m1);
        pthread_mutex_lock(m2);
    } else {
        pthread_mutex_lock(m2);
        pthread_mutex_lock(m1);
    }
}
```

### Kesalahan 3: Asumsi bahwa `volatile` Menyediakan Sinkronisasi Thread
Banyak insinyur C pemula berasumsi kata kunci `volatile` membuat variabel aman untuk konkuren.
* *Kenyataan:* `volatile` dalam bahasa C hanya memberi tahu compiler untuk tidak mengoptimalkan pembacaan variabel ke dalam register; ia **TIDAK** memancarkan *atomic instructions* dan **TIDAK** memancarkan *hardware memory barriers*. Gunakan selalu `<stdatomic.h>`, bukan `volatile`.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Selalu Setel Atribut Error Checking pada Debug Builds:**
   Gunakan atribut mutex rekursif atau pemeriksa kesalahan untuk menangkap *double locking* sejak dini:
   ```c
   pthread_mutexattr_t attr;
   pthread_mutexattr_init(&attr);
   pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_ERRORCHECK);
   pthread_mutex_init(&mutex, &attr);
   pthread_mutexattr_destroy(&attr);
   ```
2. **Karantina Critical Section:**
   Pertahankan segmen kritis sesingkat mungkin. Jangan pernah melakukan panggilan I/O file, komunikasi soket jaringan, atau alokasi memori berbobot besar di dalam blok yang memegang mutex.
3. **Gunakan RAII-Like Macro Patterns jika Memungkinkan:**
   C tidak memiliki destruktor otomatis seperti C++, namun GCC/Clang mendukung atribut ekstensi `__attribute__((cleanup))` untuk mengimplementasikan *scope-based unlocking*, mengurangi risiko lupa membuka kunci saat keluar dari percabangan fungsi (*early return*).
4. **Validasi Alokasi Thread Stack:**
   Jika sistem Anda membuat ribuan thread, jangan biarkan alokasi stack default (sering kali 8 MB per thread pada Linux). Setel ukuran stack secara manual menggunakan `pthread_attr_setstacksize(&attr, 512 * 1024)` untuk menghemat *virtual address space*.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Fenomena False Sharing & Solusi Padding Cache Line
*False Sharing* adalah pembunuh performa paling berbahaya pada arsitektur modern multicore. Fenomena ini terjadi ketika dua thread pada core yang berbeda memodifikasi variabel independen yang secara kebetulan berada dalam satu baris cache memori (*Cache Line*, umumnya 64 byte) yang sama.

```
                     +----------------------------------------+
Cache Line (64 byte) | thread_0_counter | thread_1_counter    |
                     +----------------------------------------+
                               ^                    ^
                          Diakses Core 0       Diakses Core 1
```

Setiap kali Core 0 menulis ke `thread_0_counter`, seluruh baris cache 64-byte dibatalkan (*invalidated*) pada Core 1. Core 1 terpaksa memuat ulang baris cache dari memori utama, melumpuhkan efisiensi L1/L2 cache secara drastis meskipun tidak ada *logical data race*.

#### Mitigasi dengan `alignas`:
Gunakan penyejajaran data standar C11 (`alignas` dari `<stdalign.h>`):

```c
#include <stdalign.h>

#define CACHE_LINE_SIZE 64

typedef struct {
    alignas(CACHE_LINE_SIZE) atomic_size_t core0_metrics;
    alignas(CACHE_LINE_SIZE) atomic_size_t core1_metrics;
} HighlyOptimizedMetrics;
```
Struktur di atas menjamin bahwa `core0_metrics` dan `core1_metrics` berada pada blok 64-byte yang sepenuhnya terpisah, menghilangkan latensi transfer bus antar-inti CPU.

---

# SEKSI 16 — KEAMANAN & HARDENING

1. **Pencegahan Integer Overflow pada Komputasi Heap Thread:**
   Saat menghitung ukuran alokasi untuk banyak thread, pastikan tidak terjadi overflow:
   ```c
   size_t total_mem;
   if (__builtin_mul_overflow(num_workers, sizeof(WorkerContext), &total_mem)) {
       // Tangani kesalahan overflow secara aman
       return -EOVERFLOW;
   }
   ```
2. **Menangani Sinyal Secara Aman (Signal Handling in Multithreaded Apps):**
   Jangan pernah menggunakan `signal()` biasa di dalam aplikasi multithreaded. Sinyal yang dikirim ke proses dapat dieksekusi secara nondeterministik oleh *thread* mana pun.
   * *Standar Industri:* Blokir semua sinyal asinkron pada *main thread* sebelum thread pekerja dibuat menggunakan `pthread_sigmask()`. Buat satu thread khusus yang bertugas menangkap sinyal secara sinkron melalui `sigwait()`.
3. **Pembersihan Mutex Saat Thread Dibatalkan (`pthread_cancel`):**
   Jika menggunakan pembatalan thread, daftarkan fungsi pembersih melalui `pthread_cleanup_push()` untuk memastikan mutex dilepaskan secara andal jika thread dihentikan mendadak, mencegah terjadinya kebuntuan permanen pada thread lain.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Deteksi Race Condition Menggunakan ThreadSanitizer (TSan)
ThreadSanitizer adalah instrumentasi compiler mutakhir dari Google/LLVM yang terintegrasi di dalam GCC dan Clang. TSan memantau seluruh akses memori runtime dan memverifikasi sinkronisasi inter-thread.

```bash
# Kompilasi dengan instrumentasi TSan
gcc -std=c11 -fsanitize=thread -g fundamental_concurrency.c -o tsan_demo

# Jalankan biner. TSan akan mencetak trace detail jika terjadi Data Race
./tsan_demo
```

Jika terjadi pelanggaran, TSan akan menampilkan:
* Stack trace operasi penulisan (*Write*).
* Stack trace operasi pembacaan bentrok (*Previous Read/Write*).
* ID thread dan alokasi stack yang terlibat.

### 2. Inspeksi Runtime Melalui GDB (GNU Debugger)
Perintah kunci untuk menginvestigasi *deadlock* dan status thread:

```text
(gdb) info threads
  Id   Target Id                  Frame 
* 1    Thread 0x7ffff7d9b740 (LWP 5421) __futex_abstimed_wait_common ()
  2    Thread 0x7ffff759a700 (LWP 5422) __futex_abstimed_wait_common ()

(gdb) thread apply all bt
# Mencetak seluruh call stack dari semua thread secara bersamaan.
# Memungkinkan identifikasi instan thread mana yang memegang mutex dan thread mana yang hang.

(gdb) thread 2
# Berpindah fokus inspeksi ke Thread 2
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### API Primitives POSIX Threads
```c
#include <pthread.h>

// Manajemen Siklus Hidup Thread
int pthread_create(pthread_t *t, const pthread_attr_t *a, void *(*func)(void*), void *arg);
int pthread_join(pthread_t t, void **retval);
int pthread_detach(pthread_t t);
void pthread_exit(void *retval);

// Mutex (Mutual Exclusion)
int pthread_mutex_init(pthread_mutex_t *m, const pthread_mutexattr_t *a);
int pthread_mutex_lock(pthread_mutex_t *m);
int pthread_mutex_trylock(pthread_mutex_t *m); // Non-blocking
int pthread_mutex_unlock(pthread_mutex_t *m);
int pthread_mutex_destroy(pthread_mutex_t *m);

// Condition Variables
int pthread_cond_init(pthread_cond_t *c, const pthread_condattr_t *a);
int pthread_cond_wait(pthread_cond_t *c, pthread_mutex_t *m); // Release m, sleep, re-acquire m
int pthread_cond_signal(pthread_cond_t *c);    // Wakeup minimal 1 thread
int pthread_cond_broadcast(pthread_cond_t *c); // Wakeup seluruh thread penunggu
int pthread_cond_destroy(pthread_cond_t *c);
```

### API Primitives C11 Atomics
```c
#include <stdatomic.h>

// Tipe Data: atomic_int, atomic_long, atomic_bool, atomic_uintptr_t, dll.
void atomic_init(volatile A *obj, C val);
void atomic_store_explicit(volatile A *obj, C des, memory_order order);
C    atomic_load_explicit(const volatile A *obj, memory_order order);
C    atomic_fetch_add_explicit(volatile A *obj, M arg, memory_order order);
bool atomic_compare_exchange_strong_explicit(volatile A *obj, C *exp, C des, 
                                             memory_order succ, memory_order fail);
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Ujilah penguasaan materi konkurensi Anda melalui pertanyaan diagnostik di bawah ini:

### Tingkat Dasar (Basic)
1. **Soal:** Apa perbedaan mendasar antara memanggil `pthread_join()` dan `pthread_detach()` pada sebuah thread yang baru dibuat?
   * *Jawaban:* `pthread_join()` menunda eksekusi thread pemanggil hingga target thread berhenti dan mengambil status kembalian nilainya serta membebaskan sumber daya thread tersebut. Sementara `pthread_detach()` mengonfigurasi thread agar segera setelah ia berhenti, seluruh sumber dayanya langsung dibebaskan secara otomatis oleh sistem operasi tanpa bisa di-*join* lagi.
2. **Soal:** Mengapa kita tidak boleh memeriksa predikat kondisi menggunakan blok `if` pada variabel kondisi (`pthread_cond_wait`)?
   * *Jawaban:* Karena adanya fenomena *spurious wakeup* (thread dapat terbangun tanpa adanya sinyal) dan kondisi kompetisi antar thread ketika terbangun (thread lain mungkin telah mengambil data terlebih dahulu sebelum thread ini sempat berjalan). Evaluasi wajib menggunakan loop `while`.
3. **Soal:** Mengapa kompilasi program yang menggunakan POSIX Threads pada GCC membutuhkan argumen `-pthread` dan bukan sekadar `-lpthread`?
   * *Jawaban:* Opsi `-pthread` tidak hanya mengaitkan pustaka runtime thread pada tahap linking (`-lpthread`), namun juga mendefinisikan flag pra-prosesor penting (seperti `_REENTRANT`) yang memastikan pustaka standar C menggunakan varian fungsi yang *thread-safe*.
4. **Soal:** Apakah operasi `counter++` pada tipe data `int` aman dijalankan oleh dua thread secara bersamaan jika sistem dijalankan pada prosesor dengan core tunggal (single-core CPU)? Jelaskan!
   * *Jawaban:* Tetap **TIDAK AMAN**. Meskipun core tunggal, sistem operasi melakukan *preemptive time-slicing context switch*. Jika context switch terjadi di antara instruksi mesin pembacaan register dan penulisan kembali, *lost update* tetap akan terjadi.
5. **Soal:** Apa fungsi dari fungsi `pthread_mutex_trylock()` dan kapan sebaiknya fungsi ini digunakan?
   * *Jawaban:* Fungsi ini berusaha mengambil kunci mutex tanpa memblokir/menidurkan eksekusi thread jika mutex sedang dipegang pihak lain (langsung mengembalikan error `EBUSY`). Digunakan untuk alur kerja non-blocking, polling, atau untuk menghindari potensi *deadlock*.

### Tingkat Menengah (Intermediate)
6. **Soal:** Apa dampak arsitektural dari *Memory Order Relaxed* (`memory_order_relaxed`) pada C11 atomics terhadap instruksi memori non-atomik di sekitarnya?
   * *Jawaban:* Tidak memberikan efek pembatasan (*barrier*) sama sekali. Baik compiler maupun prosesor bebas mengatur ulang (*reorder*) pembacaan dan penulisan variabel non-atomik sebelum atau sesudah operasi relaxed atomic tersebut. Hanya atomisitas variabel itu sendiri yang dijamin.
7. **Soal:** Jelaskan bagaimana instruksi `FUTEX_WAIT` dan `FUTEX_WAKE` bekerja pada level kernel Linux untuk menghemat siklus CPU pada `pthread_mutex`!
   * *Jawaban:* Fast-path mutex dieksekusi di user space via atomic CAS. Hanya jika terjadi kontensi (gagal mengunci), thread memanggil `sys_futex` dengan `FUTEX_WAIT`, memindahkan thread ke dalam kernel wait queue dan menonaktifkannya dari penjadwalan CPU. Pemilik mutex akan memanggil `FUTEX_WAKE` saat unlock untuk memindahkan thread penunggu kembali ke daftar eksekusi penjadwal kernel.
8. **Soal:** Apa bahaya dari fenomena *Priority Inversion* pada sistem berbasis thread dan bagaimana mekanisme POSIX memitigasinya?
   * *Jawaban:* Terjadi ketika thread prioritas rendah memegang mutex yang dibutuhkan thread prioritas tinggi, namun thread prioritas rendah ini terhalang eksekusinya oleh thread prioritas menengah. POSIX memitigasinya melalui protokol *Priority Inheritance* (`PTHREAD_PRIO_INHERIT`), di mana thread pemilik kunci sementara waktu mewarisi prioritas tertinggi dari thread yang sedang menunggunya.
9. **Soal:** Mengapa alokasi memori dinamis (`malloc`/`free`) di dalam segmen kritis yang sering dipanggil dapat merusak kinerja throughput pada aplikasi multithreaded skala besar?
   * *Jawaban:* Meskipun implementasi `malloc` modern menggunakan arena terpisah per core, alokasi memori internal tetap membutuhkan sinkronisasi internal kernel atau locks ketika arena kehabisan blok contiguous memory. Hal ini menambah latensi nondeterministik di dalam critical section.
10. **Soal:** Bagaimana *Cache Line Invalidation* mempengaruhi performa program saat terjadi fenomena *False Sharing*?
    * *Jawaban:* Setiap kali suatu inti prosesor memodifikasi suatu byte dalam baris cache 64-byte, protokol MESI memancarkan sinyal invalidasi ke seluruh cache bus prosesor. Core lain yang memiliki salinan baris cache tersebut harus menghapus cache line-nya dan menarik ulang data mentah dari L3 Cache atau RAM utama, menghasilkan penalti latensi ratusan siklus CPU.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "High-Performance Thread-Safe Memory Arena Pool"

### Deskripsi Masalah
Alokasi memori dinamis sistem (`malloc`) memiliki *overhead* yang cukup besar dalam sistem konkuren intensif. Anda ditugaskan untuk merancang dan membangun sistem alokasi memori bertingkat berbasis blok tetap (*Fixed-Size Chunk Memory Pool*) yang berkecepatan tinggi dan aman digunakan oleh puluhan *worker threads* secara simultan.

### Spesifikasi Teknis yang Wajib Dipenuhi
1. **Struktur Data:** Bangun struktur data `MemoryPool` yang mengalokasikan satu blok memori besar (*Slab*) di awal saat inisialisasi menggunakan `malloc(total_chunks * chunk_size)`.
2. **Koleksi Chunk Bebas (Free List):** Kelola daftar chunk yang tersedia menggunakan struktur data *Singly-Linked Free List*.
3. **Mekanisme Konkurensi:**
   * **Implementasi Varian A (Mutex-based):** Gunakan `pthread_mutex_t` untuk mengamankan operasi `pool_alloc()` dan `pool_free()`.
   * **Implementasi Varian B (Lock-Free Atomics):** Implementasikan *Push* dan *Pop* pada Free List menggunakan `atomic_compare_exchange_weak_explicit` C11 dengan semantik *Acquire-Release* memory ordering.
4. **Proteksi False Sharing:** Pastikan metadata pool dan header tiap node chunk sejajar dengan batas garis cache prosesor 64-byte (`alignas(64)`).
5. **Verifikasi Kinerja:** Tulis rutin pengujian (*benchmark harness*) yang mempekerjakan 8 thread untuk melakukan 1.000.000 operasi alokasi dan dealokasi secara acak. Ukur durasi waktu eksekusi presisi tinggi menggunakan `clock_gettime(CLOCK_MONOTONIC, ...)`.
6. **Kriteria Kelulusan:** 
   * Program tidak menghasilkan *memory leak* (diverifikasi via `valgrind --leak-check=full`).
   * Program bersih dari *data race* (diverifikasi via compilation flag `-fsanitize=thread`).
   * Varian Lock-Free harus menunjukkan peningkatan throughput minimal 30% dibandingkan varian Mutex pada kondisi kontensi tinggi.