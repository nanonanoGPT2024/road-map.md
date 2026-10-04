# BAB 08: Quiz, Challenge, & Knowledge Check
**Konkurensi, Paralelisme, dan Primitif Sinkronisasi**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Konkurensi vs. Paralelisme pada Arsitektur Modern**  
   Jelaskan perbedaan mendasar antara *concurrency* (konkurensi) dan *parallelism* (paralelisme) ditinjau dari perspektif CPU scheduler dan alokasi *hardware execution units*. Mengapa sistem yang memiliki derajat konkurensi sangat tinggi belum tentu mengeksekusi instruksi secara paralel, dan bagaimana peran *Time-Division Multiplexing* (TDM) pada sistem *single-core* dalam menciptakan ilusi simultanitas?

2. **Kondisi Coffman & Teori Deadlock**  
   Sebutkan dan bedah secara matematis/logis 4 kondisi Coffman (*Mutual Exclusion, Hold and Wait, No Preemption, Circular Wait*). Tunjukkan mengapa menghilangkan salah satu kondisi tersebut secara absolut dapat menjamin sistem bebas dari *deadlock*, serta jelaskan mengapa memecah kondisi *Circular Wait* menggunakan hierarki penguncian terurut (*lock ordering/resource hierarchy*) adalah strategi yang paling umum diimplementasikan pada level *kernel/systems programming*.

3. **Memory Models & Hardware Instruction Reordering**  
   Mengapa deklarasi variabel biasa tanpa *atomic primitives* atau *memory barriers* dapat menyebabkan data race tak terprediksi pada CPU modern, meskipun kode ditulis secara berurutan dalam bahasa tingkat tinggi? Jelaskan bagaimana *Out-of-Order Execution* (OoOE) di level hardware dan optimasi kompilator (*instruction scheduling*) mengubah urutan *load* dan *store* pada arsitektur dengan model memori santai (*Weak Memory Model* seperti ARM) dibandingkan model *Total Store Order* (TSO seperti x86-64).

4. **Karakteristik Primitif Sinkronisasi: Mutex, Spinlock, dan Semaphore**  
   Bandingkan karakteristik mekanisme kerja, overhead siklus CPU, dan penggunaan konteks eksekusi (*user-space vs kernel-space transition*) antara:
   - **Mutex** (Mutual Exclusion Object) berbasis OS *futex*
   - **Spinlock** dengan instruksi *Test-and-Set* / *PAUSE*
   - **Counting Semaphore**  
   Tentukan kriteria spesifik di mana *Spinlock* jauh lebih superior dibandingkan *Mutex*, dan sebaliknya kapan *Spinlock* menjadi anti-pattern bencana bagi sistem.

5. **Critical Section Problem & Amdahl's Law**  
   Jelaskan implikasi dari Amdahl’s Law:
   $$S_{latency}(s) = \frac{1}{(1 - p) + \frac{p}{s}}$$
   terhadap desain *critical section* dalam program multithreaded. Jika sebuah subsistem basis data memiliki 15% kode yang terkunci di bawah satu *global mutex* ($1 - p = 0.15$), berapakah batas teoritis *speedup* maksimum yang dapat dicapai meskipun sistem ditambahkan hingga 128 core CPU? Apa relevansi fenomena ini terhadap desain arsitektur *fine-grained locking* atau *lock-free*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Cache Coherency & False Sharing Trap**  
   Dua thread terpisah berjalan pada dua core CPU yang berbeda. Thread A memodifikasi variabel `struct.counter_a` (uint64) dan Thread B memodifikasi `struct.counter_b` (uint64). Kedua variabel berada berdampingan secara memori dalam satu struct. Jelaskan mengapa *throughput* eksekusi kedua thread tersebut anjlok drastis akibat protokol koherensi cache (seperti MESI/MOESI) dan fenomena *False Sharing*. Bagaimana cara memverifikasi masalah ini menggunakan profiling tool (misal: `perf c2c`) dan solusi struktural apa yang harus diterapkan pada layout memori struct tersebut?

2. **Membedah Mekanisme Linux Futex (Fast Userspace Mutex)**  
   Jelaskan alur pengeksekusian sebuah `pthread_mutex_lock` berbasis Linux *futex* pada dua skenario:
   - **Uncontended case** (tidak ada thread lain yang memegang lock).
   - **Contended case** (lock sedang dipegang oleh thread lain).  
   Uraikan transisi status integer atomik di user space dan kondisi presisi apa yang memaksa eksekusi melakukan *system call* `sys_futex(..., FUTEX_WAIT, ...)` ke kernel space beserta konsekuensi latensinya (*context switch penalty*).

3. **Analisis ABA Problem pada Desain Lock-Free Stack**  
   Perhatikan implementasi *Treiber Stack* yang menggunakan instruksi atomik `Compare-And-Swap` (CAS). Uraikan skenario langkah-demi-langkah bagaimana tiga thread (Thread 1, Thread 2, Thread 3) dapat memicu **ABA Problem** yang berujung pada kerusakan pointer memori (*use-after-free* atau *silent memory corruption*). Jelaskan teknik mitigasi standar industri untuk menyelesaikan masalah ini (misalnya: *Tagged Pointers / Version Counter* atau *Hazard Pointers / Epoch-Based Reclamation*).

4. **Memory Ordering Semantics: Acquire-Release vs. Sequential Consistency**  
   Banyak pengembang secara default menggunakan `std::memory_order_seq_cst` saat memprogram atomic operations. Jelaskan perbedaan semantik dan dampak performa antara `memory_order_seq_cst` dengan pasangan `memory_order_acquire` / `memory_order_release`. Dalam skenario komunikasi *Producer-Consumer Single-Variable Flag*, instruksi *memory ordering* mana yang paling optimal secara instruksi mesin pada arsitektur ARM64? Tunjukkan instruksi *barrier* (misal: `dmb`, `ldar`, `stlr`) yang diinjeksi oleh kompilator.

5. **Investigasi Priority Inversion & Thread Starvation**  
   Sebuah sistem real-time mengalami kegagalan kritis di mana Thread dengan prioritas tinggi (*High-Priority Thread*) terhambat mengeksekusi tugasnya secara tak terbatas karena menunggu resource yang dipegang oleh Thread berprioritas rendah (*Low-Priority Thread*), sementara Thread berprioritas menengah (*Medium-Priority Thread*) mendominasi CPU execution time. Jelaskan anomali *Priority Inversion* ini dan bagaimana mekanisme **Priority Inheritance Protocol** (PIP) serta **Priority Ceiling Protocol** (PCP) menyelesaikan deadlock fungsional tersebut di level kernel scheduler.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Skala Besar (Lock Contention pada High-Throughput In-Memory Engine)
Sebuah sistem *In-Memory Caching Engine* terdistribusi mengalami degradasi performa drastis ketika beban request dinaikkan dari 50.000 RPS ke 500.000 RPS pada server bare-metal 64-core AMD EPYC. Metrik CPU menunjukkan utilisasi 100% pada semua core, tetapi *useful throughput* (RPS) anjlok hingga 70%, dan metrik kernel mencatat lonjakan drastis pada `context-switches` (mencapai jutaan per detik) serta waktu terbuang di kernel space (`%sys` CPU time > 65%). Profiling menggunakan `perf record` menunjukkan 60% siklus CPU habis di fungsi internal `__lll_lock_wait` dan `futex_wait`.
- **Pertanyaan Diagnostik:**
  1. Identifikasi akar masalah (*root cause*) arsitektur sinkronisasi pada aplikasi tersebut yang menyebabkan *lock contention storm* ini.
  2. Mengapa penambahan jumlah thread worker secara linier justru memperburuk throughput aplikasi pada kondisi ini?
  3. Rancang strategi arsitektural konkret untuk merekayasa ulang sistem tersebut (evaluasi pendekatan: *Striped/Sharded Locking*, *Read-Copy-Update* (RCU), atau arsitektur *Thread-per-Core Share-Nothing* seperti Seastar/DPDK).

### Skenario B: Race Condition & Data Corruption (Double-Check Locking Anomaly)
Sebuah payment gateway memproses transaksi menggunakan singleton class lazy-initialized yang dikembangkan secara in-house:
```cpp
// Pseudo-C++ / Java style
class PaymentProcessor {
private:
    static PaymentProcessor* instance;
    static Mutex mtx;
    // state internals
public:
    static PaymentProcessor* getInstance() {
        if (instance == nullptr) { // Check 1
            mtx.lock();
            if (instance == nullptr) { // Check 2
                instance = new PaymentProcessor();
            }
            mtx.unlock();
        }
        return instance;
    }
};
```
Dalam stress test dengan konkurensi ekstrem, sesekali terjadi insiden `SIGSEGV` (*Segmentation Fault*) atau transaksi diproses dengan *state processor* yang kosong/parsial (nilai field masih bernilai default/sampah memori), meskipun pengecekan pointer `instance != nullptr` telah lolos.
- **Pertanyaan Diagnostik:**
  1. Buktikan secara teknis bagaimana *Double-Checked Locking Pattern* (DCLP) di atas mengalami kegagalan pada level *instruction reordering* kompilator dan prosesor! Uraikan urutan eksekusi *allocation, constructor execution,* dan *pointer assignment*.
  2. Mengapa `volatile` (pada Java/C#) atau `std::atomic` dengan *Acquire-Release semantics* (pada C++11 ke atas) wajib digunakan di sini?
  3. Tuliskan perbaikan kode (*idiomatic concurrent code*) yang 100% thread-safe dan optimal tanpa mengorbankan performa saat instance sudah terinisialisasi.

### Skenario C: Arsitektur & Trade-off Sistem (Worker Pool Architecture vs. Event-Loop Actor)
Tim platform Anda sedang merancang ulang subsistem matching engine finansial yang membutuhkan latensi p99.99 di bawah 50 mikrodetik. Terdapat perdebatan teknis sengit antara dua kubu arsitek:
- **Kubu 1:** Mengusulkan *Multi-threaded Shared-State Model* menggunakan C++20 dengan thread pool, concurrent skip-list/queue, dan sinkronisasi granular (*fine-grained lock-free CAS primitives*).
- **Kubu 2:** Mengusulkan *Single-Threaded Event Loop / Actor Model* (mirip LMAX Disruptor architecture) di mana seluruh mutasi state buku order dieksekusi secara serial murni oleh satu thread yang dipin (*CPU affinity/core isolation*) ke satu core isolir, sementara I/O network ditangani thread terpisah via ring buffer lock-free.
- **Pertanyaan Diagnostik:**
  1. Bandingkan trade-off mendalam dari kedua pendekatan tersebut ditinjau dari: latensi ekstrim (tail latency jitter), cache pollution/invalidation, kompleksitas verifikasi kebenaran kode (*correctness verification*), dan pemanfaatan hardware multi-core.
  2. Dalam domain matching engine finansial dengan order dependent state, mengapa pendekatan Kubu 2 sering kali mengalahkan pendekatan Kubu 1 dalam performa riil dan determinisme latensi?
  3. Pada kondisi beban kerja (*workload characteristics*) seperti apa pendekatan Kubu 1 justru menjadi pilihan yang lebih superior dibandingkan Kubu 2?

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi Multi-Producer Single-Consumer (MPSC) Lock-Free Bounded Ring Buffer

#### Problem Statement
Dalam infrastruktur logging dan telemetry performa tinggi, ribuan thread aplikasi (*Producers*) harus mengirimkan metrik dan log event ke satu thread I/O disk flusher (*Consumer*) tanpa memicu blocking, kernel context switch, atau lock contention yang memperlambat alur eksekusi aplikasi utama. Anda ditugaskan membangun primitif antrean data **MPSC Lock-Free Bounded Queue** dari nol (tanpa library pihak ketiga).

#### Requirements
1. **Thread-Safety & Lock-Free Guarantee:**
   - Metode `enqueue()` harus bersifat *lock-free* dan aman dipanggil oleh *N* threads secara konkuren menggunakan primitif atomik (`Compare-And-Swap` / `fetch_add` / `atomic_compare_exchange`). Tidak boleh ada penggunaan `pthread_mutex`, spinlock loop berbasis flag, atau sleep primitive di jalur *enqueue*.
   - Metode `dequeue()` hanya dipanggil oleh satu thread consumer (*Single Consumer*).
2. **Bounded Buffer & Memory Layout:**
   - Kapasitas buffer harus dibatasi hingga ukuran $2^n$ (power of two) untuk memungkinkan operasi modulo cepat via bitwise AND mask (`index & (capacity - 1)`).
   - Struktur data harus menerapkan padding eksplisit (`alignas(64)` atau setara dengan ukuran *CPU Cache Line*) antara write index, read index, dan buffer storage untuk menjamin **nol False Sharing**.
3. **Correct Memory Ordering:**
   - Gunakan *explicit memory order semantics* (`memory_order_relaxed`, `memory_order_acquire`, `memory_order_release`). Penggunaan `memory_order_seq_cst` secara membabi buta dilarang guna meminimalkan penalti instruksi bus locking pada arsitektur non-x86.
4. **Behavior on Full / Empty Buffer:**
   - `enqueue()` harus mengembalikan status `false` secara instan (*non-blocking reject/drop/backoff*) jika ring buffer penuh.
   - `dequeue()` harus mengembalikan status `empty/false` jika tidak ada elemen untuk dikonsumsi.

#### Constraints
- Bahasa Implementasi: Modern C++ (C++17/C++20), Rust, atau Go (menggunakan package `sync/atomic` dan `unsafe` pointer memory alignment).
- Alokasi memori internal: Alokasikan memori ring buffer satu kali di awal (*pre-allocated flat array*). Nol alokasi dinamis (`malloc`/`new`) pada siklus runtime *enqueue* dan *dequeue*.

#### Expected Output & Deliverables
1. **Source Code:** Berkas implementasi kelas/struct ring buffer lengkap dengan unit test fungsional.
2. **Microbenchmark & Profiling Result:**
   - Hasil benchmark throughput (ops/sec) dengan 1, 4, 8, dan 16 producer threads yang bersaing melakukan write simultan.
   - Analisis performa cache-miss menggunakan hardware performance counters (`perf stat -e L1-dcache-load-misses,L1-dcache-store-misses,cache-misses`).
3. **Dokumentasi Formal:** Diagram memori ring buffer dan pembuktian formal bahwa urutan instruksi *Acquire-Release* pada pointer baca/tulis menjamin data terisi penuh sebelum dapat dibaca oleh consumer.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara konkurensi (struktur program) dan paralelisme (eksekusi hardware fisik).
- [ ] Empat kondisi Coffman penyebab deadlock dan teknik pencegahannya (*lock hierarchy*, *try-lock backoff*).
- [ ] Cara kerja CPU Cache Coherence (MESI/MOESI), struktur Cache Line (umumnya 64 bytes), dan bahaya laten *False Sharing*.
- [ ] Perbedaan instruksi atomik CPU (*atomic load, store, CAS/Compare-And-Swap, Fetch-And-Add*) dibanding operasi non-atomik.
- [ ] Konsep *Memory Models* hardware (TSO vs. Weak Ordering) dan efek *Compiler/CPU Instruction Reordering*.
- [ ] Semantik Memori C++11 / Standar Industri: *Relaxed*, *Consume*, *Acquire*, *Release*, *Acquire-Release*, dan *Sequential Consistency*.
- [ ] Mekanisme internal primitives: Mutex (Kernel Futex), Spinlock, Semaphore, Condition Variable, dan Read-Write Lock.
- [ ] Masalah klasik konkurensi: *ABA Problem*, *Priority Inversion*, *Deadlock*, *Livelock*, dan *Starvation*.
- [ ] Batasan teoritis skalabilitas paralel melalui Amdahl's Law dan Gustafson's Law.

### Saya tidak perlu menghafal:
- [ ] Nilai numerik persis opcode biner dari instruksi assembly CPU untuk locking (misal: hex value dari opcode `LOCK CMPXCHG` atau `SWP`).
- [ ] Tanda tangan (*signature*) parameter fungsi spesifik system call `sys_futex` di kernel Linux secara verbatim di luar kepala (cukup memahami flag operasional intinya: `FUTEX_WAIT`, `FUTEX_WAKE`).
- [ ] Implementasi algoritma sinkronisasi historis kuno yang tidak lagi digunakan di CPU modern (misal: Dekker's Algorithm atau Peterson's Algorithm untuk $N$-process murni software tanpa bantuan atomic CPU).

### Saya harus bisa melakukan:
- [ ] Menggunakan debugging tools konkurensi seperti **ThreadSanitizer** (`-fsanitize=thread` pada GCC/Clang) atau Valgrind Helgrind untuk melacak data race tersembunyi.
- [ ] Menganalisis *thread dump* dan *core dump* produksi menggunakan GDB/LLDB untuk mengidentifikasi rantai saling kunci (*circular wait deadlock analysis*).
- [ ] Mendiagnosis dan mengukur contention lock serta false sharing pada level kernel/hardware menggunakan `perf` (`perf stat`, `perf record`, `perf c2c`).
- [ ] Mendesain struktur data konkuren berkinerja tinggi dengan memory alignment dan padding cache line eksplisit.
- [ ] Menulis kode sinkronisasi bebas data race dengan memilih primitif sinkronisasi yang memiliki trade-off paling rasional sesuai karakteristik beban kerja sistem.