# BAB 09: Quiz, Challenge, & Knowledge Check
**Konkurensi POSIX Threads, Sinkronisasi, & Model Atomics**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Eksekusi Utas vs Proses
Jelaskan perbedaan mendasar antara pembuatan proses melalui `fork()` dan instansiasi utas (*thread*) melalui `pthread_create()` pada kernel Linux modern (mengacu pada implementasi `sys_clone`). Bagaimana pemetaan memori (*virtual memory layout*) dikelola untuk masing-masing konteks, khususnya terkait:
- Segmentasi Text, Data, BSS, dan Heap.
- Alokasi Call Stack untuk setiap utas baru dan mekanisme penempatan Guard Page.
- Penyimpanan data spesifik utas (*Thread-Local Storage* / TLS) di level *User Space* dan *Kernel Space*.

### Soal 1.2: Formalisme Data Race vs Race Condition
Dalam ISO/IEC 9899:2011 (C11), istilah *Data Race* didefinisikan secara presisi dan berbeda secara semantik dengan *Race Condition*.
- Definisikan kriteria formal yang menyebabkan suatu eksekusi program C diklasifikasikan memiliki *Data Race*. Mengapa standar C mengategorikan *Data Race* sebagai *Undefined Behavior* (UB), dan apa implikasi optimasi kompilator jika UB ini terpicu?
- Berikan contoh kode ringkas di mana sebuah program bebas dari *Data Race* (menggunakan primitif sinkronisasi yang valid), tetapi tetap memiliki cacat arsitektur berupa *Race Condition* (*Check-Then-Act flaw*).

### Soal 1.3: Analisis Komparatif: Mutex vs Spinlock
Analisis perbedaan operasional antara `pthread_mutex_t` dan `pthread_spinlock_t`:
- Bagaimana alur transisi status utas ketika mengalami kegagalan akuisisi *lock* pada kedua primitif tersebut?
- Ditinjau dari biaya *context switch* kernel, latensi penjadwalan (*scheduling latency*), dan konsumsi daya CPU, jelaskan kapan penggunaan *spinlock* secara objektif lebih unggul dibanding *mutex*, serta kapan *spinlock* menjadi anti-pola yang merusak performa pada sistem *time-shared uniprocessor* maupun *oversubscribed multiprocessor*.

### Soal 1.4: Semantik Condition Variable dan Fenomena Spurious Wakeup
Fungsi `pthread_cond_wait()` selalu dipasangkan dengan `pthread_mutex_t` dan dieksekusi di dalam iterasi `while (!predicate)` alih-alih `if (!predicate)`.
- Jelaskan secara mekanistik apa yang dilakukan `pthread_cond_wait` terhadap *mutex* terkait saat utas mulai diblokir dan saat utas dibangunkan kembali secara atomik.
- Mengapa fenomena *Spurious Wakeup* dapat terjadi pada implementasi POSIX Threads di level sistem operasi, dan mengapa pengecekan predikat menggunakan konstruksi `if` merupakan pelanggaran fatal konkurensi?

### Soal 1.5: Taksonomi C11 Atomics Memory Model
C11 memperkenalkan pustaka `<stdatomic.h>` dengan 6 model konsistensi memori (*memory orders*). Jelaskan perbedaan teoritis dan batasan sinkronisasi antara ketiga kategori berikut:
1. `memory_order_relaxed`
2. Pasangan `memory_order_release` dan `memory_order_acquire` (*Acquire-Release Semantics*)
3. `memory_order_seq_cst` (*Sequentially Consistent*)

Sertakan penjelasan mengenai konsep relasi *synchronizes-with* dan *happens-before* yang dibentuk oleh model-model tersebut.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Mekanisme Internal Linux Futex (Fast Userspace Mutex)
Implementasi modern NPTL (*Native POSIX Thread Library*) pada Linux menggunakan primitif kernel `futex(2)` sebagai fondasi `pthread_mutex_t`.
- Bedah alur eksekusi saat operasi penguncian berada pada *uncontended path* (jalur cepat di *user space*) vs *contended path* (jalur lambat yang melibatkan *system call*).
- Instruksi atomik assembly apa yang biasanya dieksekusi oleh CPU pada fase *uncontended*? Mengapa arsitektur ini meminimalkan overhead *system call boundary crossing* secara signifikan?

### Soal 2.2: Fenomena False Sharing dan Cache Line Bouncing
Pada arsitektur CPU multicore modern dengan protokol koherensi *cache* MESI/MOESI:
- Jelaskan bagaimana fenomena *False Sharing* dapat terjadi pada struktur data `struct WorkerStats { uint64_t task_count; uint64_t error_count; };` yang dimutasi oleh dua utas independen pada core yang berbeda.
- Bagaimana dampak *Cache Line Bouncing* terhadap latensi instruksi L1 *Data Cache* dan performa konkurensi keseluruhan?
- Tunjukkan cara remediasi masalah ini secara portabel pada C11 menggunakan spesifikasi perataan memori (*memory alignment*) dan *padding*.

### Soal 2.3: Reordering Instruksi, Memory Fences, dan Perbedaan Arsitektur Hardware
Kompilator dan CPU melakukan penataan ulang instruksi (*instruction reordering*) demi memaksimalkan instruksi per siklus (*pipeline IPC*).
- Jelaskan perbedaan arsitektur memori berkarakter *Strongly Ordered* (contoh: x86-64 TSO - *Total Store Order*) dengan arsitektur berkarakter *Weakly Ordered* (contoh: ARMv8-A, RISC-V) terkait visibilitas operasi *Store-Store* dan *Store-Load*.
- Mengapa sebuah implementasi algoritma *Lock-Free* berbasis instruksi *relaxed/plain reads-writes* yang tampak berjalan sukses pada mesin pengembang berbasis Intel/AMD x86-64 dapat langsung mengalami korupsi data intermiten ketika dikompilasi dan dijalankan pada prosesor ARM?

### Soal 2.4: Masalah Deadlock dan Priority Inversion pada Utas Real-Time
Dalam sistem konkuren berbasis penguncian (*lock-based*):
- Sebutkan 4 kondisi Coffman yang mutlak diperlukan agar *deadlock* terjadi, dan jelaskan teknik *lock ordering/hierarchy* untuk memutus salah satu kondisi tersebut secara deterministik.
- Jelaskan bahaya *Priority Inversion* pada skenario thread bertingkat prioritas (Low, Medium, High). Bagaimana mekanisme *Priority Inheritance Protocol* (`PTHREAD_PRIO_INHERIT`) pada konfigurasi atribut mutex POSIX bekerja untuk memulihkan kestabilan sistem?

### Soal 2.5: Metodologi Deteksi Data Race: ThreadSanitizer (TSan) vs Helgrind
Ketika melacak bug konkurensi laten (*Heisenbugs*):
- Bagaimana ThreadSanitizer (Clang/GCC `-fsanitize=thread`) memantau eksekusi program di waktu eksekusi (*runtime*) menggunakan *shadow memory* dan pelacakan relasi *happens-before*?
- Apa perbedaan pendekatan TSan dibandingkan dengan Valgrind-Helgrind yang berbasis pelacakan algoritma *Lockset (Eraser)*?
- Sebutkan jenis bug konkurensi yang **tidak** dapat dideteksi secara otomatis oleh TSan.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Ekstrem pada Transaksi Finansial
Sebuah sistem *Matching Engine* bursa kripto berlatensi mikrodetik diimplementasikan dalam C murni. Arsitektur lama menggunakan struktur data antrean tunggal (*Order Book Queue*) yang diproteksi oleh sebuah `pthread_mutex_t`. Di bawah beban puncak 250.000 transaksi/detik pada peladen berspesifikasi 64 core CPU (dual-socket NUMA), observasi *profiling* menggunakan `perf` menunjukkan:
- Penggunaan CPU 95% terserap pada fungsi `__lll_lock_wait` dan siklus *kernel scheduling*.
- Metrik *throughput* kolaps sebesar 80% dibanding saat pengujian dengan 4 core.
- Terjadi fenomena *NUMA remote-node access latency* yang tinggi saat utas pada Socket 1 mencoba mengakses mutex yang diinisialisasi pada memori lokal Socket 0.

**Pertanyaan Diagnostik:**
1. Lakukan audit teknis menyeluruh: mengapa desain *centralized mutex* mengalami degradasi performa eksponensial saat jumlah core CPU bertambah pada sistem NUMA?
2. Usulkan desain ulang arsitektur struktur data antrean transaksi tersebut tanpa menggunakan *global mutex*. Struktur antrean konkurensi apa yang tepat, dan bagaimana strategi alokasi memori lokal NUMA (`numa_alloc_onnode` / `mmap`) diterapkan untuk mengisolasi mutasi memori pada masing-masing soket CPU?

---

### Skenario B: Heisenbug "Double-Free / Memory Corruption" pada AWS Graviton (ARM64)
Sebuah *High-Throughput In-Memory Cache Engine* yang dikembangkan pada mesin Linux x86-64 berjalan stabil di lingkungan produksi selama bertahun-tahun. Ketika tim infrastruktur melakukan migrasi sistem ke kluster cloud bertenaga AWS Graviton (arsitektur ARM64), sistem mulai mengalami *SIGSEGV* acak dan laporan korupsi memori (*double-free*) setiap beberapa juta permintaan data.
Setelah isolasi kode, ditemukan modul *Reference Counter* berikut yang digunakan untuk siklus hidup objek memori:

```c
typedef struct {
    void *data;
    atomic_int refcount;
} CacheNode;

void retain(CacheNode *node) {
    atomic_fetch_add_explicit(&node->refcount, 1, memory_order_relaxed);
}

void release(CacheNode *node) {
    // BUG POTENSIAL DI SINI:
    if (atomic_fetch_sub_explicit(&node->refcount, 1, memory_order_relaxed) == 1) {
        free(node->data);
        free(node);
    }
}
```

**Pertanyaan Diagnostik:**
1. Bedah secara mendalam mengapa kode di atas bekerja tanpa cacat pada mesin x86-64 (TSO), tetapi mengalami korupsi memori fatal pada arsitektur ARM64 yang memiliki *Weak Memory Ordering*. Operasi memori apa yang diizinkan untuk dibalik urutannya (*reordered*) oleh prosesor ARM pada implementasi di atas?
2. Perbaiki kode implementasi fungsi `release()` menggunakan model konsistensi memori C11 yang benar (`memory_order_release`, `memory_order_acquire`, atau kombinasi `atomic_thread_fence`). Buktikan mengapa solusi Anda menjamin bahwa semua pembacaan dan penulisan terhadap `node->data` sebelum `release()` selesai secara deterministik sebelum fungsi `free()` dieksekusi.

---

### Skenario C: Dilema Arsitektur: Actor-Model Lock-Free Ring Buffer vs Thread-Pool Shared State
Anda ditunjuk sebagai Principal Architect untuk merancang subsistem agregasi metrik telemetri yang harus menerima data dari 1.000 utas koneksi jaringan (*Worker Threads*) dan mengirimkannya ke 1 utas penulis disk/jaringan (*Flusher Thread*). Volume pesan rata-rata adalah 10.000.000 metrik per detik.
Dua pendekatan arsitektur diajukan oleh tim:
- **Pendekatan 1:** Utas jaringan langsung memasukkan paket ke dalam sebuah *Circular Buffer* raksasa yang diproteksi oleh *Pthread Read-Write Lock* (`pthread_rwlock_t`).
- **Pendekatan 2:** Arsitektur *Multi-Producer Single-Consumer (MPSC)* yang terdistribusi, di mana setiap *Worker Thread* memiliki *Single-Producer Single-Consumer (SPSC) Lock-Free Ring Buffer* berukuran tetap, dan *Flusher Thread* melakukan *round-robin polling* ke setiap buffer menggunakan C11 Atomics.

**Pertanyaan Diagnostik:**
1. Bandingkan kedua pendekatan tersebut dari perspektif:
   - *Lock Contention* dan latensi *tail* (p99.9).
   - Kompleksitas *cache-coherence traffic* pada *Interconnect Bus* (QPI/UPI/Infinity Fabric).
   - Risiko *Starvation* pada utas pekerja.
2. Manakah pendekatan yang Anda pilih untuk beban kerja telemetri masif ini? Sertakan justifikasi matematis/mekanis terkait *Amdahl's Law* dan *Universal Scalability Law* (USL) untuk memperkuat keputusan Anda.

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi High-Performance Lock-Free SPSC Ring Buffer dengan C11 Atomics

#### Problem Statement
Dalam pemrosesan data berkecepatan tinggi (*High-Frequency Trading*, pemrosesan audio waktu-nyata, atau penanganan paket jaringan DPDK), latensi penguncian (*mutex lock overhead*) dan alokasi memori dinamis di jalur kritis (*hot path*) tidak dapat ditoleransi. Anda diminta membangun komponen perangkat lunak fundamental tingkat produksi: **Bounded Lock-Free Single-Producer Single-Consumer (SPSC) Queue** murni dalam C11 standar.

#### Technical Requirements
1. **API Interface**: Sediakan antarmuka ringkas pada berkas `spsc_queue.h` dan implementasi pada `spsc_queue.c`:
   - `spsc_queue_t* spsc_init(size_t capacity);`
   - `void spsc_destroy(spsc_queue_t *queue);`
   - `bool spsc_enqueue(spsc_queue_t *queue, void *item);` (Non-blocking, kembalikan `false` jika penuh)
   - `bool spsc_dequeue(spsc_queue_t *queue, void **item);` (Non-blocking, kembalikan `false` jika kosong)
2. **Kapasitas Power-of-Two**: Kapasitas antrean harus dibulatkan ke nilai perpangkatan dua terdekat ($2^N$) agar operasi modulo indeks sirkular dapat digantikan dengan operasi bitwise mask (`index & (capacity - 1)`).
3. **Penyelarasan Cache (*Cache Alignment*) & Anti-False Sharing**:
   - Struktur data harus memisahkan indeks penulisan (*head*) dan indeks pembacaan (*tail*) ke dalam *cache line* yang berbeda menggunakan `alignas(64)` (atau konstanta `hardware_destructive_interference_size`).
4. **Semantik Memori C11 yang Presisi**:
   - Dilarang keras menggunakan `memory_order_seq_cst` karena inefisiensi instruksi *full memory barrier* (seperti `MFENCE` pada x86 atau `DMB ISH` pada ARM).
   - Gunakan kombinasi `memory_order_relaxed`, `memory_order_release`, dan `memory_order_acquire` secara optimal untuk mutasi dan visibilitas penunjuk *head* dan *tail*.
5. **Zero Allocation**: Operasi `enqueue` dan `dequeue` tidak boleh memanggil `malloc()`, `free()`, maupun *system call* kernel apa pun. Jalur kritis eksekusi harus sepenuhnya berjalan di *user space* dengan kompleksitas $O(1)$.

#### Constraints
- Kode harus lolos kompilasi bersih tanpa *warning* menggunakan *flags*:
  `gcc -std=c11 -Wall -Wextra -Werror -pedantic -O3 -pthread`
- Harus tervalidasi bersih tanpa kesalahan konkurensi di bawah:
  `gcc -fsanitize=thread -g`
- Dilarang menggunakan *library* konkurensi pihak ketiga atau primitif OS-spesifik selain standar ISO C11 `<stdatomic.h>` dan POSIX threads `<pthread.h>` (hanya untuk pengujian *harness*).

#### Expected Output & Verification
Buat program pengujian (*benchmarking harness*) `main.c` yang:
1. Menginisiasi 1 utas *Producer* dan 1 utas *Consumer*.
2. Memproses transfer $50.000.000$ pointer data integer secara sukses.
3. Mencetak metrik:
   - Total waktu eksekusi (milidetik).
   - *Throughput* (Operasi per detik / Mops).
   - Validasi integritas data: Konsumen harus memverifikasi bahwa seluruh rangkaian bilangan yang diterima urut monotonik naik tanpa ada data yang hilang atau terduplikasi ($0, 1, 2, \dots, 49.999.999$).
4. Menjalankan *stress test* di bawah eksekutor ThreadSanitizer untuk membuktikan ketiadaan *Data Race* secara matematis dan empiris.

---

## 5. Knowledge Check & Checklist

Gunakan daftar periksa ini untuk memvalidasi kesiapan kompetensi Anda pada ranah konkurensi tingkat lanjut.

### Saya harus memahami:
- [ ] Perbedaan model memori antara thread (ruang alamat virtual terbagi) dan proses (ruang alamat terisolasi/CoW).
- [ ] Definisi formal ISO C11 *Data Race*, implikasi *Undefined Behavior*, dan mengapa membaca/menulis `int` non-atomik multi-utas adalah bug fatal.
- [ ] Siklus hidup dan status eksekusi POSIX Threads (`pthread_create`, `pthread_join`, `pthread_detach`).
- [ ] Alur kerja primitif sinkronisasi kernel: semantik Futex, Fast-path (User-space CAS) vs Slow-path (Kernel deschedule).
- [ ] Prinsip kerja protokol koherensi cache (MESI/MOESI) dan penyebab munculnya degradasi akibat *False Sharing*.
- [ ] Konsep penataan ulang instruksi (*compiler & CPU out-of-order execution*) serta perbedaan arsitektur memori *Strong* (TSO) vs *Weak*.
- [ ] Taksonomi C11 Atomics: `memory_order_relaxed`, `acquire`, `release`, dan `seq_cst` beserta model graf *Happens-Before*.
- [ ] Akar penyebab masalah sistemik: *Deadlock* (Kondisi Coffman), *Livelock*, *Thread Starvation*, dan *Priority Inversion*.

### Saya tidak perlu menghafal:
- [ ] Nilai numerik konstan dari atribut `pthread_attr_set*` atau konstanta `errno` (misal: `EDEADLK`, `EBUSY`, `ETIMEDOUT`). Cukup lihat dokumentasi manual (`man 3 pthread_mutex_lock`).
- [ ] Implementasi internal kode assembly CPU untuk instruksi atomik spesifik arsitektur (seperti `CMPXCHG16B` atau `LDREX/STREX`), karena telah diabstraksikan oleh intrinsik kompilator C11 `<stdatomic.h>`.
- [ ] Nomor syscall spesifik untuk operasi `futex` pada kernel Linux di berbagai varian CPU.

### Saya harus bisa melakukan:
- [ ] Menggunakan `pthread_mutex` dan `pthread_cond_t` secara benar dengan membungkus `wait` di dalam loop evaluasi status predikat.
- [ ] Mengonfigurasi dan memanfaatkan alat instrumentasi dinamis modern: ThreadSanitizer (`-fsanitize=thread`) dan Valgrind (`--tool=helgrind` / `--tool=drd`) untuk membedah masalah konkurensi.
- [ ] Menggunakan `alignas(64)` untuk mengisolasi variabel atomik pada *cache line* independen guna mengeliminasi *False Sharing*.
- [ ] Menerapkan algoritma sinkronisasi *Lock-Free* sederhana (SPSC Ring Buffer atau Atomic Reference Counter) menggunakan C11 `<stdatomic.h>` secara aman tanpa *data race*.
- [ ] Menganalisis *bottleneck* penguncian sistem multi-core menggunakan utilitas performa Linux tingkat lanjut (`perf top`, `perf record`, dan visualisasi *FlameGraph*).