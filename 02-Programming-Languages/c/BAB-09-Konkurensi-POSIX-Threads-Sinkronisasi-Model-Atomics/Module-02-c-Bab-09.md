# Kurikulum Rekayasa Sistem Perangkat Lunak: C Enterprise-Grade
## Bab 09: Konkurensi POSIX Threads, Sinkronisasi & Model Atomics
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, *Software Engineer* dan *Systems Architect* memiliki kompetensi untuk:

1. **Menganalisis dan Memilih Model Konsistensi Memori (Memory Consistency Models):** Membedakan dan mengimplementasikan model memori C11 (`memory_order_relaxed`, `memory_order_acquire`, `memory_order_release`, `memory_order_acq_rel`, `memory_order_seq_cst`) pada arsitektur perangkat keras *strongly-ordered* (x86 TSO) dan *weakly-ordered* (ARMv8, POWER).
2. **Merancang Struktur Data Bebas Kunci (*Lock-Free Data Structures*):** Mengimplementasikan primitif *Single-Producer Single-Consumer* (SPSC) dan *Multi-Producer Multi-Consumer* (MPMC) *ring buffer* berbasis *Compare-And-Swap* (CAS) tanpa *deadlock* dan *priority inversion*.
3. **Mengeliminasi Penalti Koherensi Cache (*Cache Coherence Degradation*):** Mendeteksi serta memitigasi *false sharing* dan utilisasi interkoneksi bus QPI/UPI melalui penataan *data layout*, *cacheline padding* (`alignas(64)`), dan isolasi *core affinity* (`pthread_setaffinity_np`).
4. **Menangani Siklus Hidup Memori Bebas Kunci:** Menerapkan strategi resolusi *ABA Problem* dan manajemen *safe memory reclamation* menggunakan *Epoch-Based Reclamation* (EBR) atau *Hazard Pointers*.
5. **Memvalidasi dan Melakukan Profiling Concurrency Produksi:** Mengintegrasikan LLVM *ThreadSanitizer* (TSan), Valgrind Helgrind/DRD, serta *hardware performance counters* (`perf c2c`) ke dalam *pipeline build enterprise*.

---

### 2. Prerequisite

Peserta wajib menguasai:
* Primitif dasar POSIX Threads: `pthread_create`, `pthread_join`, `pthread_mutex_t`, `pthread_cond_t`.
* Pointer indirection tingkat lanjut: *Double pointers*, *type punning*, *volatile qualifier* semantics.
* Arsitektur CPU dasar: Register, L1/L2/L3 Cache, bus memori, instruksi per siklus (IPC).
* Standar C: Minimal C11 (`-std=c11` atau `-std=gnu11`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Hardware Memory Subsystems & Cache Coherence (MESI/MOESI)

Pada komputasi modern multi-inti (*multi-core*), CPU tidak berkomunikasi langsung dengan DRAM secara sinkron karena adanya latensi ratusan siklus CPU. Setiap *core* memiliki cache lokal (L1i, L1d, L2) dan berbagi L3 Cache. Konsistensi data antar-cache dijamin oleh protokol berbasis *hardware* seperti MESI (*Modified, Exclusive, Shared, Invalid*) atau variasinya (MOESI, MESIF).

```
+-----------------------------------------------------------------------+
|                              DRAM                                     |
+-----------------------------------------------------------------------+
                                   ^
                                   | QPI / UPI / Infinity Fabric
                                   v
+-----------------------------------------------------------------------+
|                           L3 Cache (Shared)                           |
+-----------------------------------------------------------------------+
                   ^                                 ^
                   |                                 |
        +----------+----------+           +----------+----------+
        v                     v           v                     v
  +-----------+         +-----------+   +-----------+         +-----------+
  | L2 Cache  |         | L2 Cache  |   | L2 Cache  |         | L2 Cache  |
  +-----------+         +-----------+   +-----------+         +-----------+
        ^                     ^               ^                     ^
        |                     |               |                     |
  +-----------+         +-----------+   +-----------+         +-----------+
  | L1d Cache |         | L1d Cache |   | L1d Cache |         | L1d Cache |
  +-----------+         +-----------+   +-----------+         +-----------+
        ^                     ^               ^                     ^
        |                     |               |                     |
  +-----------+         +-----------+   +-----------+         +-----------+
  | Store Buf |         | Store Buf |   | Store Buf |         | Store Buf |
  +-----------+         +-----------+   +-----------+         +-----------+
        ^                     ^               ^                     ^
  +-----------+         +-----------+   +-----------+         +-----------+
  |  Core 0   |         |  Core 1   |   |  Core 2   |         |  Core 3   |
  +-----------+         +-----------+   +-----------+         +-----------+
```

1. **Store Buffers:** Core mengeksekusi instruksi *store* ke dalam buffer lokal sebelum cache line dialokasikan atau diubah ke status *Modified* (*Write Invalidations* dikirim ke core lain). Ini memungkinkan eksekusi *Out-of-Order* berlanjut tanpa menunggu konfirmasi dari bus.
2. **Invalidate Queues:** Core penerima pesan *invalidation* menaruh pesan tersebut di antrean dan langsung mengonfirmasi penerimaan tanpa mengeksekusi *invalidation* seketika. Konsekuensi: Core tersebut dapat membaca data *stale* dari cache-nya sendiri hingga antrean dikosongkan.

#### 3.2. C11 Memory Models & Semantics

Standar ISO C11 memperkenalkan `<stdatomic.h>` untuk menstandardisasi operasi konkuren pada tingkat bahasa tanpa bergantung pada *inline assembly* spesifik arsitektur.

| Memory Order | Deskripsi Operasi | Penggunaan Tipikal | Overhead Hardware (x86) | Overhead Hardware (ARM64) |
| :--- | :--- | :--- | :--- | :--- |
| `memory_order_relaxed` | Hanya menjamin atomisitas modifikasi pada alamat terkait. Tidak ada jaminan ordering terhadap operasi memori lain. | Counter statistik, progress bar | Nol (sama dengan mov biasa) | Nol |
| `memory_order_acquire` | Mencegah pembacaan/penulisan setelah operasi ini di-reorder sebelum operasi ini (*Load-Load* & *Load-Store* barrier). | Lock acquisition, Consumer reads | Nol (implisit pada TSO) | Instruksi `dmb.ld` atau `ldar` |
| `memory_order_release` | Mencegah penulisan/pembacaan sebelum operasi ini di-reorder setelah operasi ini (*Store-Store* & *Load-Store* barrier). | Lock release, Producer writes | Nol (implisit pada TSO) | Instruksi `dmb.ish` atau `stlr` |
| `memory_order_acq_rel` | Gabungan *acquire* dan *release*. | Operasi Read-Modify-Write (RMW) seperti `fetch_add`, CAS | Nol (jika instruksi lock terpakai) | Rangkaian `ldaxr`/`stlxr` |
| `memory_order_seq_cst` | *Sequential Consistency*. Menyediakan ordering global total untuk semua operasi yang diberi label ini. | Default C11, algoritma safety-critical | Instruksi `lock` prefix / `mfence` | Instruksi `dmb.ish` |

#### 3.3. Linux Kernel Futex Under the Hood

POSIX Mutex pada implementasi modern glibc tidak mengeksekusi *syscall* jika tidak terjadi kontensi. Arsitektur ini memanfaatkan primitif Linux **Futex** (*Fast Userspace Mutex*).

1. **Jalur Cepat (*Fast Path*):** Menggunakan instruksi CPU atomik (misalnya CAS / `atomic_compare_exchange_strong`) langsung di *userspace*. Jika *unlocked*, *lock* diambil tanpa *context switch* ke kernel mode (biaya: ~10-25 nanodetik).
2. **Jalur Lambat (*Slow Path*):** Jika kontensi terdeteksi, *thread* memanggil sistem operasi melalui *syscall* `sys_futex(uaddr, FUTEX_WAIT, val, ...)`. Kernel menempatkan *thread* ke dalam *wait queue* berbasis *hash bucket* dan menjadwalkan *thread* lain (*descheduling*). Saat *thread* pemilik melepaskan *lock*, ia memanggil `sys_futex(uaddr, FUTEX_WAKE, 1, ...)`.

---

### 4. Why & What

#### Mengapa Primitif Berbasis Kunci (Mutex) Gagal pada Skala Ekstrim?
* **Konvoi Thread (*Thread Convoying*):** Jika *thread* yang memegang mutex mengalami *preemption* oleh *kernel scheduler* (karena kehabisan *time slice* atau *page fault*), semua *thread* lain yang mengantre akan terblokir.
* **Overhead Konteks (*Context Switch Overhead*):** Perpindahan *user-to-kernel mode* memakan waktu 1.000 hingga 1.500 siklus CPU, ditambah hilangnya *cache locality* (L1 TLB miss, I-cache miss).
* **Inversi Prioritas (*Priority Inversion*):** *Thread* prioritas rendah memegang *lock* yang dibutuhkan *thread* prioritas tinggi, sementara *thread* prioritas menengah berjalan, menyebabkan *unbounded latency*.

#### Apa Solusinya?
* **Lock-Free Synchronization:** Menjamin bahwa setidaknya satu *thread* di dalam sistem membuat *progress* dalam sejumlah langkah komputasi terhingga (*system-wide progress guarantee*).
* **Wait-Free Synchronization:** Menjamin bahwa **setiap** *thread* membuat *progress* dalam sejumlah langkah terhingga (*per-thread progress guarantee*).
* **Cache-Aligned Data Layouts:** Mengisolasi data yang dimodifikasi oleh *core* berbeda ke *cacheline* terpisah (umumnya 64 byte pada arsitektur x86/ARM) untuk menghilangkan *Cache Thrashing*.

---

### 5. How (Workflow Detail)

Alur kerja sinkronisasi *Acquire-Release* antar dua thread tanpa *sequential consistency global lock*:

```
           Thread A (Producer)                       Thread B (Consumer)
         =======================                   =======================
         
         data_payload = 0xDEADBEEF;                
         [Store to Payload Memory]                 
                    |                              
                    v                              
         atomic_store_explicit(                    
             &flag, 1,                             
             memory_order_release);                
                    |                              
                    +----------------------------------------+
                    | (Inter-thread Happens-Before Edge)     |
                    +----------------------------------------+
                                                             |
                                                             v
                                                   while (atomic_load_explicit(
                                                              &flag, 
                                                              memory_order_acquire) == 0) {
                                                       // Spin wait / pause
                                                   }
                                                             |
                                                             v
                                                   uint32_t val = data_payload;
                                                   [Read Payload Guaranteed 0xDEADBEEF]
```

1. **Fase 1 (Producer Local Write):** Thread A memodifikasi *non-atomic buffer* atau data terstruktur.
2. **Fase 2 (Producer Release Barrier):** Thread A melakukan *store* pada variabel kontrol atomik dengan `memory_order_release`. Compiler dan CPU dicegah memindahkan penulisan dari Fase 1 melewati batas ini. *Store Buffer* di-flush sesuai aturan model memori arsitektur.
3. **Fase 3 (Consumer Acquire Barrier):** Thread B membaca variabel kontrol dengan `memory_order_acquire`.
4. **Fase 4 (Safe Access):** Melalui relasi *synchronizes-with*, semua modifikasi memori yang dilakukan Thread A sebelum rilis atomik dijamin terlihat (*visible*) oleh Thread B setelah operasi *acquire* berhasil.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan dua teknisi di fasilitas perakitan: Teknisi A (Producer) merakit mesin di atas meja kerja, lalu menyalakan lampu sinyal hijau (*Release Flag*). Teknisi B (Consumer) hanya boleh mendekati dan menguji mesin tersebut saat lampu sinyal menyala (*Acquire Flag*). 
Jika teknisi menyalakan lampu sebelum mesin selesai dirakit (akibat *CPU instruction reordering* tanpa *barrier*), Teknisi B akan menguji komponen yang belum terpasang sempurna, menyebabkan kegagalan sistem.

#### False Sharing vs Cache-Line Alignment

Kasus Terkontaminasi: *False Sharing* (Kedua Core memperebutkan baris cache yang sama).
```
+-------------------------------------------------------------------+
|               L1 Data Cacheline (Ukuran: 64 Byte)                 |
|  +-------------------------------+-----------------------------+  |
|  | Core 0 memodifikasi: var_a   | Core 1 memodifikasi: var_b  |  |
|  | (Offset 0x00 - 0x07)         | (Offset 0x08 - 0x0F)        |  |
|  +-------------------------------+-----------------------------+  |
+-------------------------------------------------------------------+
  ^                                 ^
  | Invalidasi Bus Tiap Write       | Invalidasi Bus Tiap Write
  +---------------------------------+
```

Kasus Optimal: *Cache-Line Padding* (`alignas(64)`).
```
+-------------------------------------------------------------------+
|               L1 Data Cacheline X (Ukuran: 64 Byte)               |
|  +-------------------------------------------------------------+  |
|  | Core 0 memodifikasi: var_a (Offset 0x00 - 0x07)             |  |
|  | PADDING KOSONG (Offset 0x08 - 0x3F)                         |  |
|  +-------------------------------------------------------------+  |
+-------------------------------------------------------------------+

+-------------------------------------------------------------------+
|               L1 Data Cacheline Y (Ukuran: 64 Byte)               |
|  +-------------------------------------------------------------+  |
|  | Core 1 memodifikasi: var_b (Offset 0x00 - 0x07)             |  |
|  | PADDING KOSONG (Offset 0x08 - 0x3F)                         |  |
|  +-------------------------------------------------------------+  |
+-------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Producer-Consumer Menggunakan Model Memori C11

Kode ini mendemonstrasikan transfer data non-atomik menggunakan jaminan *happens-before* dari sinkronisasi *Acquire-Release*.

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <pthread.h>
#include <stdint.h>

typedef struct {
    uint64_t data_payload[4];
} WorkItem;

static WorkItem g_shared_payload;
static atomic_bool g_is_ready = ATOMIC_VAR_INIT(false);

void* producer_thread(void* arg) {
    (void)arg;
    
    // Inisialisasi payload data non-atomik
    g_shared_payload.data_payload[0] = 0x1122334455667788ULL;
    g_shared_payload.data_payload[1] = 0xAABBCCDDEEFF0011ULL;
    g_shared_payload.data_payload[2] = 0x0123456789ABCDEFULL;
    g_shared_payload.data_payload[3] = 0xFEDCBA9876543210ULL;

    // memory_order_release: Memastikan SEMUA store sebelumnya terlihat
    // oleh thread lain yang melakukan load dengan memory_order_acquire.
    atomic_store_explicit(&g_is_ready, true, memory_order_release);

    return NULL;
}

void* consumer_thread(void* arg) {
    (void)arg;

    // Menunggu sinyal siap dengan acquire semantics
    while (!atomic_load_explicit(&g_is_ready, memory_order_acquire)) {
        #if defined(__x86_64__) || defined(_M_X64)
            __builtin_ia32_pause(); // Mencegah pipeline stall akibat spin loop
        #elif defined(__aarch64__)
            __asm__ volatile("yield" ::: "memory");
        #endif
    }

    // Aman membaca data non-atomik: Tidak akan membaca kondisi setengah terisi
    printf("Consumer membaca payload[0]: 0x%lX\n", g_shared_payload.data_payload[0]);
    printf("Consumer membaca payload[3]: 0x%lX\n", g_shared_payload.data_payload[3]);

    return NULL;
}

int main(void) {
    pthread_t prod, cons;

    if (pthread_create(&cons, NULL, consumer_thread, NULL) != 0) {
        perror("pthread_create consumer");
        return EXIT_FAILURE;
    }

    if (pthread_create(&prod, NULL, producer_thread, NULL) != 0) {
        perror("pthread_create producer");
        return EXIT_FAILURE;
    }

    pthread_join(prod, NULL);
    pthread_join(cons, NULL);

    return EXIT_SUCCESS;
}
```

#### 7.2. Practical Example: Production Lock-Free SPSC Ring Buffer

Arsitektur antrean cincin (*ring buffer*) *Single-Producer Single-Consumer* (SPSC) berperforma ultra-tinggi yang dirancang khusus untuk meminimalkan *false sharing* dengan mengisolasi indeks producer dan consumer ke dalam *cacheline* terpisah menggunakan `alignas(64)`.

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdalign.h>
#include <stdatomic.h>
#include <pthread.h>
#include <string.h>
#include <assert.h>
#include <errno.h>

#define CACHELINE_SIZE 64
#define BUFFER_CAPACITY 65536 // Wajib kelipatan 2^N untuk masking cepat
#define BUFFER_MASK (BUFFER_CAPACITY - 1)

typedef struct {
    uint64_t transaction_id;
    double price;
    uint32_t quantity;
    char symbol[8];
} MarketTick;

typedef struct {
    // Cacheline 1: Dibaca & Ditulis oleh Producer, Dibaca oleh Consumer
    alignas(CACHELINE_SIZE) atomic_size_t tail; 
    alignas(CACHELINE_SIZE) size_t cached_head; // Optimasi: simpanan lokal producer

    // Cacheline 2: Dibaca & Ditulis oleh Consumer, Dibaca oleh Producer
    alignas(CACHELINE_SIZE) atomic_size_t head;
    alignas(CACHELINE_SIZE) size_t cached_tail; // Optimasi: simpanan lokal consumer

    // Storage buffer terpisah dari baris kontrol antrean
    alignas(CACHELINE_SIZE) MarketTick buffer[BUFFER_CAPACITY];
} SPSCQueue;

SPSCQueue* spsc_create(void) {
    SPSCQueue* q = aligned_alloc(CACHELINE_SIZE, sizeof(SPSCQueue));
    if (!q) {
        perror("Gagal mengalokasikan memory ring buffer");
        return NULL;
    }
    atomic_init(&q->tail, 0);
    atomic_init(&q->head, 0);
    q->cached_head = 0;
    q->cached_tail = 0;
    return q;
}

void spsc_free(SPSCQueue* q) {
    free(q);
}

bool spsc_enqueue(SPSCQueue* q, const MarketTick* item) {
    const size_t current_tail = atomic_load_explicit(&q->tail, memory_order_relaxed);
    
    // Periksa kapasitas menggunakan cached_head untuk mengurangi bus-load
    if ((current_tail - q->cached_head) >= BUFFER_CAPACITY) {
        q->cached_head = atomic_load_explicit(&q->head, memory_order_acquire);
        if ((current_tail - q->cached_head) >= BUFFER_CAPACITY) {
            return false; // Antrean penuh
        }
    }

    // Tulis data ke buffer lokal
    q->buffer[current_tail & BUFFER_MASK] = *item;

    // Pastikan payload tersimpan sebelum memperbarui penanda tail untuk Consumer
    atomic_store_explicit(&q->tail, current_tail + 1, memory_order_release);
    return true;
}

bool spsc_dequeue(SPSCQueue* q, MarketTick* item) {
    const size_t current_head = atomic_load_explicit(&q->head, memory_order_relaxed);

    // Periksa apakah antrean kosong menggunakan cached_tail
    if (current_head == q->cached_tail) {
        q->cached_tail = atomic_load_explicit(&q->tail, memory_order_acquire);
        if (current_head == q->cached_tail) {
            return false; // Antrean kosong
        }
    }

    // Ambil data
    *item = q->buffer[current_head & BUFFER_MASK];

    // Pastikan data telah dibaca sebelum membebaskan slot bagi Producer
    atomic_store_explicit(&q->head, current_head + 1, memory_order_release);
    return true;
}

// ------------------- Uji Skala Produksi -------------------

#define TOTAL_TRANSACTIONS 50000000ULL

void* producer_worker(void* arg) {
    SPSCQueue* q = (SPSCQueue*)arg;
    MarketTick tick = {
        .price = 101.50,
        .quantity = 500,
        .symbol = "IDR/USD"
    };

    for (uint64_t i = 0; i < TOTAL_TRANSACTIONS; ++i) {
        tick.transaction_id = i;
        while (!spsc_enqueue(q, &tick)) {
            #if defined(__x86_64__)
                __builtin_ia32_pause();
            #elif defined(__aarch64__)
                __asm__ volatile("yield" ::: "memory");
            #endif
        }
    }
    return NULL;
}

void* consumer_worker(void* arg) {
    SPSCQueue* q = (SPSCQueue*)arg;
    MarketTick tick;
    uint64_t consumed_count = 0;

    while (consumed_count < TOTAL_TRANSACTIONS) {
        if (spsc_dequeue(q, &tick)) {
            assert(tick.transaction_id == consumed_count);
            consumed_count++;
        } else {
            #if defined(__x86_64__)
                __builtin_ia32_pause();
            #elif defined(__aarch64__)
                __asm__ volatile("yield" ::: "memory");
            #endif
        }
    }
    return NULL;
}

int main(void) {
    SPSCQueue* queue = spsc_create();
    assert(queue != NULL);

    pthread_t prod_t, cons_t;
    
    printf("Menjalankan SPSC Lock-Free Ring Buffer Benchmark: %llu transaksi...\n", 
           (unsigned long long)TOTAL_TRANSACTIONS);

    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);

    pthread_create(&cons_t, NULL, consumer_worker, queue);
    pthread_create(&prod_t, NULL, producer_worker, queue);

    pthread_join(prod_t, NULL);
    pthread_join(cons_t, NULL);

    clock_gettime(CLOCK_MONOTONIC, &end);

    double elapsed_sec = (double)(end.tv_sec - start.tv_sec) + 
                         (double)(end.tv_nsec - start.tv_nsec) / 1e9;

    printf("Selesai memproses %llu pesan dalam %.3f detik.\n", 
           (unsigned long long)TOTAL_TRANSACTIONS, elapsed_sec);
    printf("Throughput: %.2f Juta Operasi/detik\n", 
           ((double)TOTAL_TRANSACTIONS / elapsed_sec) / 1e6);

    spsc_free(queue);
    return EXIT_SUCCESS;
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Pada sistem *High-Frequency Trading* (HFT) atau *Matching Engine* bursa berjangka, *Order Gateway* menerima paket protokol FIX (*Financial Information eXchange*) dari ratusan klien secara paralel melalui antarmuka *Kernel-Bypass Networking* (misalnya Solarflare OpenOnload atau DPDK).

#### Permasalahan Arsitektur
Desain awal menggunakan antrean berbasis `pthread_mutex_t` dan `pthread_cond_t` untuk mengalirkan order masuk ke satu *Core Matching Engine*. Saat volume perdagangan melonjak pada rilis data inflasi (misalnya US CPI), sistem mengalami:
1. P99.9 Latensi melonjak dari **800 nanodetik** menjadi **4.2 milidetik**.
2. Profiling *Linux perf* menunjukkan 73% waktu siklus CPU habis di fungsi kernel `futex_wait_setup` dan `native_queued_spin_lock_slowpath`.
3. Terjadi *cache invalidation storm* pada interkoneksi UPI antar *NUMA node*.

#### Solusi Rekayasa
1. **Pemisahan Jalur Komunikasi ke Arsitektur SPSC:** Mengganti MPMC Mutex Queue dengan arsitektur *Decoupled Core*. Setiap *Network Worker Core* dialokasikan satu SPSC Lock-Free Queue berarah tunggal ke *Matching Engine Core*.
2. **CPU Core Pinning & NUMA Affinitizing:** Mengikat worker ke NUMA socket yang sama dengan kartu jaringan menggunakan `pthread_setaffinity_np`.
3. **Penyisipan Instruksi Hardware Clflush/Pause:** Mengurangi konsumsi daya instruksi pipeline saat buffer sedang kosong menggunakan `__builtin_ia32_pause()`.
4. **Hasil Implementasi:**
   * Latensi P99.9 turun stabil menjadi **340 nanodetik** di bawah beban 15 juta order per detik.
   * Waktu *kernel-space* berkurang hingga mendekati 0%.

---

### 9. Trade-offs

| Parameter | Mutex Berbasis OS (`pthread_mutex`) | Lock-Free CAS Loop (MPMC) | Lock-Free SPSC Ring Buffer |
| :--- | :--- | :--- | :--- |
| **Throughput (Ops/sec)** | Rendah - Menengah (~2-5 M/s) | Menengah - Tinggi (~10-25 M/s) | Sangat Tinggi (> 50-100 M/s) |
| **Latensi Determinisme** | Buruk (rentan *preemption* & *syscalls*) | Variatif (tinggi jika kontensi CAS melonjak) | Deterministik murni (Sub-mikrodetik) |
| **Kompleksitas Kode** | Rendah (mudah dinalar) | Sangat Tinggi (Masalah ABA, Reordering) | Terukur (Khusus 1 Producer, 1 Consumer)|
| **Konsumsi CPU saat Idle**| 0% (Thread tertidur via kernel) | 100% jika spin-loop aktif | 100% jika spin-loop aktif |
| **Alokasi Memori** | Minimal | Kompleks (Node-based memory reclamation)| Statis / Pre-allocated Ring Array |
| **Skalabilitas Concurrency**| Menurun drastis seiring core bertambah | Menurun pada tingkat kontensi sangat tinggi | Linear per pasang core independen |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Mengasumsikan `volatile` Menyediakan Eksekusi Bersifat Atomik
* **Kesalahan:** Menggunakan `volatile int flag = 0;` sebagai mekanisme sinkronisasi multithreading di C.
* **Fakta:** Kata kunci `volatile` di C hanya memberi tahu compiler untuk tidak mengoptimasi pembacaan/penulisan register ke memori (mencegah *dead-code elimination*). `volatile` **TIDAK** memancarkan *hardware memory barriers* dan **TIDAK** menjamin atomisitas.
* **Solusi:** Gunakan tipe atomik C11 `atomic_int` atau `_Atomic`.

#### 10.2. Masalah ABA pada Node-Based Lock-Free Stack/Queue
* **Gejala:** Memory corruption dan *segmentation fault* yang tidak dapat direproduksi secara konsisten di development environment.
* **Mekanisme Bug:**
  1. Thread 1 membaca Pointer Node A (yang menunjuk ke Node B).
  2. Thread 1 terkena *preemption*.
  3. Thread 2 melepaskan (pop) Node A, melepaskan Node B, lalu membebaskan (`free`) Node A.
  4. Thread lain mengalokasikan memori baru yang kebetulan menempati alamat pointer Node A yang sama persis. Pointer top baru menunjuk ke A, tetapi top->next menunjuk ke Node C, bukan B.
  5. Thread 1 melanjutkan eksekusi CAS (`atomic_compare_exchange` pada Node A). Pengecekan pointer sama persis (A == A), CAS berhasil, namun top->next sekarang mereferensikan memori liar (*dangling pointer* B).
* **Solusi:** 
  1. Gunakan *Tagged Pointers* / *Double-Word CAS* (DW-CAS) dengan menyimpan penghitung versi (*version counter*) di samping pointer.
  2. Implementasikan *Hazard Pointers* atau *Epoch-Based Memory Reclamation*.

#### 10.3. False Sharing pada Struktur Data Konkuren
* **Penyebab:** Menyimpan variabel atomik yang sering dimodifikasi oleh thread berbeda di dalam struct yang sama tanpa padding.
* **Deteksi:** Jalankan Linux `perf`:
  ```bash
  perf c2c record -- ./nama_program_anda
  perf c2c report --stdio
  ```
* **Solusi:** Selalu tambahkan `alignas(64)` pada setiap variabel kontrol atomik thread-independen.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Sanitizer pada Pipeline CI/CD:** Wajib menyertakan flag kompilasi `-fsanitize=thread -g` pada build testing otomatis.
- [ ] **Hindari Default `memory_order_seq_cst` pada Hot Path:** Gunakan `memory_order_acquire` dan `memory_order_release` kecuali algoritma menuntut konsistensi urutan eksekusi global.
- [ ] **Alokasikan Cache-Line Padding untuk Data Inti:** Lindungi variabel pembagi thread menggunakan `alignas(64)` atau macro `__attribute__((aligned(64)))`.
- [ ] **Semua Thread Konkuren Terikat ke Core Spesifik (*Core Affinity*):** Gunakan `pthread_setaffinity_np` untuk mengunci thread ke *logical core* guna mengeliminasi migrasi OS antar L1/L2 cache.
- [ ] **Terapkan Fallback Back-off Strategy:** Jangan biarkan thread melakukan *tight infinite spin*. Gunakan instruksi hardware pause (`__builtin_ia32_pause()` pada x86 atau `yield` pada ARM) di dalam loop tunggu.
- [ ] **Static Assertion Ukuran Tipe Data:** Validasi ukuran struktur atomik saat kompilasi dengan `static_assert(sizeof(MyType) <= 8, "Struktur data tidak muat di native CPU word")`.
- [ ] **Terapkan Clean Resource Deallocation:** Pastikan *thread pool* atau *ring buffer* menyediakan API destruksi bersih yang mengosongkan sisa item dengan benar sebelum dealokasi memori buffer.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Struktur Proyek:
```
hands-on/m02/
├── Makefile
├── lockfree_spsc.h
└── main.c
```

#### File: `hands-on/m02/lockfree_spsc.h`
```c
#ifndef LOCKFREE_SPSC_H
#define LOCKFREE_SPSC_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdalign.h>
#include <stdatomic.h>

#define RING_BUFFER_SIZE 1024 // Ukuran tetap untuk latihan hands-on

typedef struct {
    uint64_t sequence;
    int32_t  payload_val;
} Element;

typedef struct {
    alignas(64) atomic_size_t write_idx;
    alignas(64) atomic_size_t read_idx;
    alignas(64) Element storage[RING_BUFFER_SIZE];
} BoundedSPSC;

void bounded_spsc_init(BoundedSPSC* q);
bool bounded_spsc_push(BoundedSPSC* q, const Element* val);
bool bounded_spsc_pop(BoundedSPSC* q, Element* out);

#endif
```

#### File: `hands-on/m02/main.c`
```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include "lockfree_spsc.h"

void bounded_spsc_init(BoundedSPSC* q) {
    atomic_init(&q->write_idx, 0);
    atomic_init(&q->read_idx, 0);
}

bool bounded_spsc_push(BoundedSPSC* q, const Element* val) {
    size_t w = atomic_load_explicit(&q->write_idx, memory_order_relaxed);
    size_t r = atomic_load_explicit(&q->read_idx, memory_order_acquire);

    if ((w - r) >= RING_BUFFER_SIZE) {
        return false; // Kapasitas penuh
    }

    q->storage[w % RING_BUFFER_SIZE] = *val;
    atomic_store_explicit(&q->write_idx, w + 1, memory_order_release);
    return true;
}

bool bounded_spsc_pop(BoundedSPSC* q, Element* out) {
    size_t r = atomic_load_explicit(&q->read_idx, memory_order_relaxed);
    size_t w = atomic_load_explicit(&q->write_idx, memory_order_acquire);

    if (r == w) {
        return false; // Kosong
    }

    *out = q->storage[r % RING_BUFFER_SIZE];
    atomic_store_explicit(&q->read_idx, r + 1, memory_order_release);
    return true;
}

static BoundedSPSC g_queue;
#define WORK_ITEMS 1000000

void* producer(void* arg) {
    (void)arg;
    for (int i = 0; i < WORK_ITEMS; ++i) {
        Element el = {.sequence = (uint64_t)i, .payload_val = i * 2};
        while (!bounded_spsc_push(&g_queue, &el)) {
            __builtin_ia32_pause();
        }
    }
    return NULL;
}

void* consumer(void* arg) {
    (void)arg;
    int received = 0;
    Element el;
    while (received < WORK_ITEMS) {
        if (bounded_spsc_pop(&g_queue, &el)) {
            if (el.sequence != (uint64_t)received || el.payload_val != received * 2) {
                fprintf(stderr, "DATA CORRUPTION TERDETEKSI DI ELEMEN %d!\n", received);
                exit(EXIT_FAILURE);
            }
            received++;
        } else {
            __builtin_ia32_pause();
        }
    }
    return NULL;
}

int main(void) {
    bounded_spsc_init(&g_queue);

    pthread_t p, c;
    pthread_create(&p, NULL, producer, NULL);
    pthread_create(&c, NULL, consumer, NULL);

    pthread_join(p, NULL);
    pthread_join(c, NULL);

    printf("Hands-on Berhasil: %d elemen diverifikasi tanpa korupsi data.\n", WORK_ITEMS);
    return 0;
}
```

#### File: `hands-on/m02/Makefile`
```makefile
CC = gcc
CFLAGS = -Wall -Wextra -O3 -std=c11 -pthread
TSAN_FLAGS = -fsanitize=thread -g

all: release tsan

release: main.c
	$(CC) $(CFLAGS) main.c -o spsc_release

tsan: main.c
	$(CC) $(CFLAGS) $(TSAN_FLAGS) main.c -o spsc_tsan

run_tsan: tsan
	./spsc_tsan

clean:
	rm -f spsc_release spsc_tsan
```

---

### 13. Exercise

#### Tingkat: Easy
Implementasikan custom spinlock menggunakan `atomic_flag` yang menyediakan antarmuka `custom_spinlock_lock()` dan `custom_spinlock_unlock()`. Spinlock harus menggunakan `atomic_flag_test_and_set_explicit` dengan `memory_order_acquire` dan `atomic_flag_clear_explicit` dengan `memory_order_release`.

#### Tingkat: Medium
Modifikasi antrean cincin SPSC hands-on menjadi Multi-Producer Single-Consumer (MPSC). Producer harus saling berkompetisi memperebutkan `write_idx` menggunakan loop `atomic_compare_exchange_weak_explicit`.

#### Tingkat: Hard
Rancang struktur data *Lock-Free Singly-Linked Stack* (Treiber Stack) yang tahan terhadap *ABA Problem* dengan mengintegrasikan representasi pointer yang dipasangkan dengan 64-bit counter (*Tagged Pointer*) menggunakan instruksi `atomic_compare_exchange` selebar 128-bit (`__int128` atau instruksi `CMPXCHG16B` pada x86_64).

---

### 14. Challenge (Studi Kasus Enterprise Tanpa Solusi Instan)

**Target Kasus:**
Rancang arsitektur mesin *Zero-Copy Telemetry Event Hub* yang menerima data matriks performa jaringan dari 32 thread worker jaringan yang berjalan paralel, dan mengirimkannya ke 4 thread penyimpanan NVMe secara asinkron.

**Batasan & Persyaratan:**
1. Throughput target: Minimal **60 Juta Events per detik** pada CPU 32-core.
2. Tidak boleh ada sistem *memory allocation* dinamis (`malloc`/`free`) saat *runtime hot-path*. Semua memori harus *pre-allocated*.
3. Latensi P99.99 tidak boleh melebihi **1.5 mikrodetik**.
4. Wajib bebas dari kemungkinan *Deadlock*, aman dari *ABA Problem*, dan terbukti bersih saat diuji menggunakan flag `-fsanitize=thread`.
5. Arsitektur harus menangani skenario di mana thread penyimpan (consumer) mengalami lag tanpa mengakibatkan pemblokiran (*block*) pada thread worker jaringan. Definisikan secara eksplisit kebijakan *overflow/drop* atau ring-swapping non-blocking yang Anda pilih.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Mengapa penambahan atribut `volatile` tidak cukup untuk variabel flag multithreading di C?**
2. **Apa yang dijamin oleh operasi baca dengan `memory_order_relaxed`?**
3. **Berapa ukuran tipikal *Cacheline* pada arsitektur modern x86 dan ARM64?**
4. **Apa fungsi macro/instruksi `__builtin_ia32_pause()` pada CPU x86 saat berada di dalam spin loop?**
5. **Jelaskan perbedaan mendasar antara kondisi *Lock-Free* dan *Wait-Free*.**

#### Bagian 2: Intermediate (5 Soal)
6. **Pada arsitektur x86 TSO (Total Store Order), mengapa `memory_order_acquire` pada operasi load secara native memiliki overhead instruksi nol?**
7. **Mengapa `atomic_compare_exchange_weak` lebih disukai di dalam perulangan `while` dibandingkan `atomic_compare_exchange_strong` pada platform ARM?**
8. **Jelaskan bagaimana *False Sharing* dapat merusak performa throughput hingga puluhan kali lipat meskipun program bebas data race.**
9. **Apa perbedaan fungsional antara `memory_order_acq_rel` dengan `memory_order_seq_cst`?**
10. **Bagaimana mekanisme kernel Linux menangani transisi dari userspace ke kernelspace ketika `pthread_mutex_lock` mengalami kontensi?**

#### Bagian 3: Skenario Kasus Produksi (3 Kasus)
11. **Skenario A:** Sebuah tim merilis sistem berbasis lock-free ring buffer yang lulus 100% unit test pada mesin Intel Core-i9. Ketika kode yang sama dikompilasi dan dijalankan di AWS Graviton (ARM64), sistem mengalami corrupt data dan segfault acak. Bagian mana yang salah dalam perancangan kode?
12. **Skenario B:** Profiling server transaksi keuangan menunjukkan beban CPU 100% pada semua core, namun metrik IOPS dan transaksi per detik sangat rendah. Setelah diinspeksi, tim menemukan ribuan thread menggunakan spinlock. Bagaimana Anda merombak arsitektur sinkronisasi ini?
13. **Skenario C:** Anda memiliki antrean lock-free berukuran dinamis yang mengalokasikan dan mendealokasikan node. ThreadSanitizer bersih, namun memory usage proses terus membengkak (leak) secara eksponensial di bawah beban 100k req/s. Apa akar masalahnya dalam konteks safe memory reclamation?

---

#### Kunci Jawaban & Rationale Evaluasi

##### Jawaban Basic
1. `volatile` hanya menginstruksikan compiler untuk tidak menyimpan nilai variabel di register CPU (selalu reload dari RAM/Cache). Ia tidak menyisipkan instruksi pembatas memori (*memory barrier*), sehingga compiler dan CPU tetap bebas melakukan *instruction reordering*. Selain itu, `volatile` tidak menjamin keterbagian instruksi (*atomicity*) baca-tulis.
2. `memory_order_relaxed` hanya menjamin operasi pada variabel tersebut dieksekusi secara atomik (tidak terjadi tearing data bit-level). Sama sekali tidak memberikan jaminan urutan eksekusi (*ordering*) relatif terhadap operasi memori di sekitarnya.
3. Ukuran standar industri adalah 64 byte.
4. Instruksi `pause` memberi petunjuk ke CPU bahwa thread sedang berada di dalam spin-wait loop. Ini mencegah de-optimasi *memory order violation pipeline* saat keluar dari loop (menghemat 30-100 siklus pipeline flush) serta mengurangi konsumsi daya listrik inti tersebut.
5. *Lock-free* menjamin sistem secara keseluruhan terus berjalan maju (setidaknya ada satu thread yang menyelesaikan tugas dalam satuan waktu), meskipun thread lain bisa saja starving. *Wait-free* memberikan jaminan lebih ketat di mana setiap individu thread dijamin membuat progres dalam sejumlah langkah terhingga tanpa terhambat thread lain.

##### Jawaban Intermediate
6. Arsitektur x86 mengimplementasikan model memori TSO (*Total Store Order*). Pada TSO, perangkat keras secara implisit melarang reordering operasi *Load-Load* dan *Load-Store*. Karena aturan perangkat keras x86 secara default sudah memenuhi kontrak aturan *acquire*, operasi *acquire load* cukup diwujudkan dengan instruksi `mov` register biasa tanpa perlu menyisipkan instruksi pagar (*fence*) tambahan.
7. Pada platform RISC/ARM yang menggunakan arsitektur *Load-Linked/Store-Conditional* (LL/SC) seperti `ldrex`/`strex`, instruksi `atomic_compare_exchange_weak` diperbolehkan gagal secara *spurious* (misalnya karena context switch atau instruksi lain yang menyela reservasi memori). Implementasi `weak` tidak memerlukan instruksi loop internal tambahan untuk menangani *spurious failure* tersebut, sehingga lebih cepat dan efisien jika digunakan di dalam konstruksi perulangan `while` yang memang sudah mengecek kondisi berulang kali.
8. CPU memuat dan memvalidasi data antar cache dalam satuan *cacheline* (64 byte). Jika dua thread pada core berbeda memodifikasi dua variabel berbeda yang secara kebetulan berada di cacheline 64-byte yang sama, protokol koherensi (MESI) akan terus-menerus membatalkan (*invalidate*) baris cache antar core tersebut secara bolak-balik melalui bus antarmuka CPU (*cache-line bouncing*), menghasilkan latensi akses setara pembacaan langsung dari DRAM.
9. `memory_order_acq_rel` mengikat relasi pemesanan data lokal hanya antara thread yang melepaskan (*release*) dan thread yang mengambil (*acquire*) data tersebut. Sebaliknya, `memory_order_seq_cst` memaksakan urutan eksekusi total tunggal (*globally consistent total order*) di seluruh CPU core yang ada di motherboard. Pada arsitektur non-TSO atau multi-socket NUMA, `seq_cst` memerlukan penyisipan *full memory fence* (seperti `mfence` atau `dmb ish`) yang memblokir instruksi pipeline CPU hingga instruksi invalidasi bus selesai dikonfirmasi.
10. Saat pertama kali dieksekusi, mutex mencoba mengambil kepemilikan via instruksi atomik (misalnya CAS) di *userspace*. Jika gagal (ada kontensi), thread membuat panggilan sistem *sys_futex* dengan operasi `FUTEX_WAIT`. Kernel memvalidasi apakah nilai di alamat memori belum berubah; jika valid, kernel memasukkan pointer thread ke dalam antrean tunggu (*wait queue* berbasis red-black tree/hash bucket kernel) dan memanggil fungsi penjadwal `schedule()` untuk menidurkan thread tersebut sehingga core CPU dapat digunakan oleh proses lain.

##### Jawaban Skenario Produksi
11. **Akar Masalah:** Developer kemungkinan menggunakan operasi `relaxed` atau pointer dereference tanpa `acquire`/`release` barrier yang tepat, atau mengabaikan perbedaan antara arsitektur TSO (Intel x86) dan Weakly Ordered (ARM64). Pada x86, pelanggaran penataan memori tersembunyi karena perangkat keras secara otomatis menegakkan urutan penulisan *Store-Store* dan pembacaan *Load-Load*. Namun saat dieksekusi di prosesor ARM64, CPU melakukan reordering agresif secara *Out-of-Order*. 
    **Solusi:** Ganti akses instruksi variabel kontrol dengan `atomic_load_explicit(..., memory_order_acquire)` dan `atomic_store_explicit(..., memory_order_release)`.
12. **Akar Masalah:** *Spinning overhead catastrophe*. Terjadi over-subscription thread atau kontensi tinggi di mana thread terus-menerus memutar siklus CPU (*busy-waiting*) memperebutkan lock yang sedang dipegang oleh thread yang telah di-preempt oleh OS scheduler. 
    **Solusi:** Terapkan teknik *Exponential Back-Off* dengan transisi berjenjang: Putar loop instruksi CPU `pause` sebanyak 10-50 kali; jika belum berhasil, panggil `sched_yield()` untuk menyerahkan time-slice; dan jika masih gagal, alihkan thread ke mekanisme tidur berbasis OS (`pthread_mutex_t` atau primitif berbasis Futex/Semaphor).
13. **Akar Masalah:** Permasalahan *Deferred Reclamation Deadlock* atau *Quiescent State Starvation*. Pada struktur data bebas-kunci dinamis, memori node yang telah di-*pop* tidak dapat langsung dieksekusi `free()` karena thread lain mungkin sedang membaca alamat pointer tersebut (membaca via hazard pointer atau terdaftar dalam *epoch window* yang sama). Di bawah beban tinggi 100k req/s, thread tidak pernah mencapai kondisi diam (*quiescent state*), sehingga fungsi pembersih *epoch reclamation* menunda penghapusan memori tanpa batas, yang berakibat pada akumulasi alokasi tak terbatas. 
    **Solusi:** Terapkan pembersihan memori berbasis batching dengan batas atas tegas (*hard cap limit*), atau beralihlah ke arsitektur memori berukuran tetap yang pre-allocated (*flat ring-buffer pool*) untuk membuang kebutuhan alokasi dinamis pada data-path produksi.

---

### 16. Summary

1. **Primitif Sinkronisasi Standar C11:** Pustaka `<stdatomic.h>` merupakan fondasi modern untuk portabilitas operasi konkuren tanpa ketergantungan pada assembler arsitektur tertentu.
2. **Kekuatan Acquire-Release Semantics:** Menjadi tulang punggung sistem komputasi berkinerja tinggi. Model ini memungkinkan transfer status memori antar-thread secara deterministik dengan biaya komputasi mendekati operasi baca-tulis memori standar tanpa penalti global *full-fence* `seq_cst`.
3. **Pemisahan Cacheline (*Hardware Locality*):** Solusi performa pada concurrency bukan hanya terletak pada ada tidaknya mutex, melainkan perancangan struktur data yang menghormati batas 64-byte *cacheline alignment* untuk mengeliminasi *false sharing*.
4. **Prinsip Arsitektur SPSC:** Bentuk komunikasi inter-thread paling optimal pada perangkat lunak produksi adalah pola *Single-Producer Single-Consumer* yang mengisolasi state thread secara tegas, membebaskan sistem dari kontensi bus perangkat keras, dan meminimalkan latensi pemrosesan hingga tingkat nanodetik.