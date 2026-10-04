# BAB 09: Quiz, Challenge, & Knowledge Check
**Bab 09: Concurrency, Multithreading, Memory Model, & Synchronization**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Distingsi Formal: *Data Race* vs *Race Condition***  
   Jelaskan perbedaan mendasar antara *Data Race* dan *Race Condition* menurut spesifikasi standar C++ (*ISO/IEC 14882*). Mengapa *Data Race* selalu berstatus *Undefined Behavior* (UB) di level bahasa, sementara *Race Condition* tingkat logika aplikasi dapat terjadi bahkan ketika seluruh akses memori telah disinkronisasi secara legal?

2. **Siklus Hidup Thread dan RAII: `std::thread` vs `std::jthread` (C++20)**  
   Analisis mekanisme destruksi pada `std::thread`. Mengapa pemanggilan destruktor pada instans `std::thread` yang masih berstatus `joinable()` memicu `std::terminate()`? Bagaimana `std::jthread` menyelesaikan masalah ini melalui paradigma RAII dan mekanisme kooperatif `std::stop_token`?

3. **Mekanika *Spurious Wakeup* pada `std::condition_variable`**  
   Mengapa pemanggilan `wait()` pada `std::condition_variable` wajib dibungkus dalam sebuah predikat *loop* (seperti `while(!ready)` atau menggunakan *overload* `cv.wait(lock, predicate)`)? Jelaskan fenomena *spurious wakeup* dari perspektif interaksi kernel OS (*futex* pada Linux atau sinyal interupsi) dan arsitektur multiprosesor.

4. **Hierarki Konsistensi Memori: Sequential Consistency vs Relaxed Ordering**  
   `std::memory_order_seq_cst` adalah nilai default pada operasi atomik C++. Bandingkan model konsistensi tersebut dengan `std::memory_order_relaxed`. Jelaskan penalti performa (dari sisi *instruction pipeline stall* dan *memory barrier/fence*) yang harus dibayar saat menggunakan *sequential consistency* pada arsitektur perangkat keras *weakly-ordered* (misalnya ARM64) dibandingkan *strongly-ordered* (x86-64).

5. **Karakteristik Primitif: `std::mutex` vs `std::atomic<T>`**  
   Kapan seorang *systems engineer* harus memilih `std::mutex` dibandingkan operasi `std::atomic`? Tinjau jawaban Anda dari aspek *overhead* transisi *user-space* ke *kernel-space*, strategi *lock contention*, dan batasan tipe data `T` (seperti *trivially copyable* dan ukuran registri CPU) agar dapat dimanipulasi secara *lock-free*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Patologi Performa: *False Sharing* dan *Cache Line Bouncing***  
   Diberikan struktur data penghitung (*counter*) global array di mana setiap thread memodifikasi indeks uniknya sendiri (`counter[thread_id]++`). Jelaskan mengapa throughput sistem mengalami degradasi drastis pada sistem *multi-socket NUMA*. Bagaimana Anda memanfaatkan `alignas` dan konstanta `std::hardware_destructive_interference_size` (C++17) untuk mengeliminasinya?

2. **Sinkronisasi *Acquire-Release* Semantics**  
   Diberikan potongan instruksi modifikasi data non-atomik yang dipublikasikan via *flag* atomik:
   ```cpp
   // Thread 1 (Producer)
   data = 42;
   ready.store(true, std::memory_order_release);

   // Thread 2 (Consumer)
   while (!ready.load(std::memory_order_acquire));
   assert(data == 42);
   ```
   Jelaskan secara presisi bagaimana relasi *synchronizes-with* dan *happens-before* terbentuk antar-thread. Mengapa kompilator dan prosesor dilarang mereorder *store* ke `data` melintasi *store release* pada `ready`?

3. **Anatomi *The ABA Problem* pada Struktur Data *Lock-Free***  
   Dalam implementasi *lock-free stack* (Treiber Stack) yang menggunakan primitive `std::atomic::compare_exchange_weak`, jelaskan skenario terjadinya *ABA Problem*. Apa dampak destructive-nya terhadap integritas *free-list/memory reuse*, dan bagaimana mitigasinya menggunakan *tagged pointers* (`double-width CAS`) atau *Hazard Pointers* / *Epoch-Based Reclamation (EBR)*?

4. **Deadlock Prevention dan Analisis Algoritmik `std::scoped_lock`**  
   Ketika sebuah thread membutuhkan akuisisi dua mutex sekaligus (`mutex_a` dan `mutex_b`), jelaskan mekanisme algoritma pencegahan *deadlock* (*deadlock avoidance*) yang dijalankan secara internal oleh `std::lock` atau `std::scoped_lock` (C++17). Mengapa pemanggilan berurutan konvensional (`lock_a.lock(); lock_b.lock();`) rentan terhadap anomali *circular wait*?

5. **Manajemen Exception di dalam Thread Boundary**  
   Jika sebuah *exception* tak tertangani (*uncaught exception*) dilempar di dalam fungsi yang dieksekusi oleh `std::thread`, apa perilaku default dari *runtime* C++? Bagaimana arsitektur penanganan *exception* yang aman antar-thread menggunakan `std::promise`, `std::future`, dan `std::current_exception()` / `std::rethrow_exception()`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Skala Besar pada Trading Engine Berlatensi Ultra-Rendah
Sebuah mesin pencocokan order (*Order Matching Engine*) HFT berbasis C++20 berjalan pada server bare-metal Linux dengan 64-core AMD EPYC. Sistem menggunakan model thread-per-worker yang membaca event dari sebuah antrean global bersama (*shared concurrent queue*) yang diproteksi oleh `std::mutex`. 

Pada beban puncak (*market open*), latensi p99 membengkak dari 800 nanodetik menjadi 45 milidetik, sementara utilisasi CPU secara agregat justru anjlok dan metrik OS melaporkan lonjakan drastis pada angka *context switches* (`voluntary_ctxt_switches`) serta *kernel lock contention* di subsistem *futex*.
* **Pertanyaan Diagnostik:**
  1. Analisis akar penyebab sistem mengalami lonjakan latensi dan penurunan utilisasi CPU saat terjadi perebutan mutex (*lock contention*) masif.
  2. Rancang ulang arsitektur komunikasi antar-thread ini untuk mencapai latensi deterministik p99 < 1 mikrodetik! Jelaskan pilihan pola arsitektur pengganti (misalnya: *Single-Producer Single-Consumer (SPSC) ring buffer lock-free*, penyematan afinitas CPU / *core pinning*, dan pemisahan arsitektur *Shared-Everything* menjadi *Shared-Nothing/Actor-like*).

---

### Skenario B: Kerusakan Memori Terdistribusi akibat Antipattern Double-Checked Locking (DCLI)
Sebuah *Distributed Telemetry Agent* mengalami *segmentation fault* intermiten yang hanya muncul setiap beberapa minggu sekali pada arsitektur ARM64 produksi, namun tidak pernah teridentifikasi di mesin pengujian lokal berbasis Intel x86-64. Investigasi kode menemukan komponen *singleton logging subsystem* berikut:

```cpp
class TelemetryLogger {
private:
    static inline TelemetryLogger* instance{nullptr};
    static inline std::mutex mtx;
    TelemetryLogger() { /* inisialisasi state berat */ }

public:
    static TelemetryLogger* get_instance() {
        if (instance == nullptr) { // Check 1
            std::lock_guard<std::mutex> lock(mtx);
            if (instance == nullptr) { // Check 2
                instance = new TelemetryLogger();
            }
        }
        return instance;
    }
};
```
* **Pertanyaan Diagnostik:**
  1. Bedah secara mendalam mengapa kode di atas mengandung *Data Race* dan berstatus *Undefined Behavior* jika ditinjau dari reordering instruksi mesin (`out-of-order execution`) pada arsitektur ARM64. Mengapa anomali ini hampir tidak pernah termanifestasi pada x86-64?
  2. Ubah implementasi fungsi tersebut agar memenuhi kaidah *thread-safe initialization* modern C++ sesuai standar *Meyers' Singleton* atau menggunakan primitif `std::call_once` / sinkronisasi atomik *acquire-release*. Tunjukkan kode perbaikannya.

---

### Skenario C: Dilema Arsitektur Database Engine: Thread Pool vs Coroutines (Work-Stealing vs Cooperative Multitasking)
Tim Anda sedang merancang ulang subsistem eksekusi query untuk *in-memory analytical execution engine*. Karakteristik beban kerja terdiri dari ribuan query paralel kecil dengan latensi sangat pendek (mikrodetik) yang diselingi tugas batch besar berkonsumsi CPU intensif.
* **Pertanyaan Diagnostik:**
  1. Bandingkan trade-off mendalam antara implementasi **Thread Pool berbasis Work-Stealing (preemptive multithreading)** vs **C++20 Asynchronous Coroutines (`co_await` stackless cooperative multitasking)** dari aspek *memory footprint*, biaya *context switching*, kompleksitas debugging/profiling, dan responsivitas penjadwalan.
  2. Bagaimana Anda menyusun strategi mitigasi jika satu tugas CPU-bound intensif memonopoli worker thread pada model *cooperative coroutines*, dan arsitektur hibrida seperti apa yang paling optimal untuk mengisolasi kedua karakteristik beban kerja tersebut?

---

## 4. Chapter Challenge
**Tantangan Praktis: Implementasi High-Throughput Lock-Free Bounded SPSC (Single-Producer Single-Consumer) Ring Buffer**

### Deskripsi Masalah
Dalam sistem komunikasi inter-thread latensi rendah (seperti *audio engine* real-time, *trading pipeline*, atau *network packet processing*), primitif penguncian berbasis kernel (`std::mutex`, `std::condition_variable`) menimbulkan latensi yang tidak deterministik akibat *syscall overhead* dan *thread preemption*. Anda ditugaskan untuk mengimplementasikan sebuah antrean data sirkular (*bounded ring buffer*) berbasis *Single-Producer Single-Consumer* (SPSC) yang sepenuhnya *lock-free* dan *wait-free*.

### Kebutuhan Teknis (Requirements)
1. **Interface Template:**
   Implementasikan kelas C++20:
   ```cpp
   template <typename T, size_t Capacity>
   class LockFreeSPSCQueue;
   ```
   di mana `Capacity` wajib berupa bilangan pangkat dua (*power of two*) yang diverifikasi saat kompilasi (*compile-time concept/assertion*).
2. **Operasi Non-Blocking:**
   - `bool push(const T& item)` dan `bool push(T&& item)`: Mengembalikan `false` secara instan jika antrean penuh (*non-blocking*).
   - `bool pop(T& value)`: Mengambil elemen terdepan ke dalam `value` dan mengembalikan `true`, atau mengembalikan `false` secara instan jika antrean kosong.
3. **Optimasi Memori & Cache:**
   - Indeks *head* (dimutasi oleh producer) dan *tail* (dimutasi oleh consumer) harus diisolasi ke dalam *cache line* yang berbeda menggunakan `alignas(std::hardware_destructive_interference_size)` untuk mencegah *False Sharing*.
   - Sinkronisasi antara producer dan consumer harus menggunakan model memori yang optimal: gunakan relasi `std::memory_order_release` saat mempublikasikan indeks, dan `std::memory_order_acquire` saat membaca indeks pasangan. Dilarang keras menggunakan `std::memory_order_seq_cst`.
4. **Zero Dynamic Allocation at Runtime:**
   Seluruh storage memori internal untuk antrean harus dialokasikan secara statis di dalam kelas (misalnya menggunakan array internal atau buffer uninitialized storage berbasis `std::aligned_storage` / byte arrays).

### Batasan (Constraints)
- Kode harus ditulis dalam standar C++20 murni.
- Tidak boleh memicu *Data Race* sekecil apa pun saat diuji di bawah alat analisis **ThreadSanitizer (TSan)** (`-fsanitize=thread`).
- Tidak boleh menggunakan pustaka eksternal seperti Boost; hanya gunakan STL standar (`<atomic>`, `<new>`, `<concepts>`, `<type_traits>`).
- Implementasi harus bersifat *noexcept* pada seluruh operasi perpindahan pointer/indeks.

### Expected Output & Pengujian
- Unit test komprehensif yang menjalankan 1 thread producer (memproduksi 10.000.000 integer terurut) dan 1 thread consumer (mengkonsumsi dan memvalidasi keutuhan serta urutan integer tersebut secara simultan).
- Verifikasi bahwa konsumsi memori stabil, tidak ada *memory leak*, dan throughput mencapai puluhan juta operasi per detik tanpa adanya assertion failure.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan formal antara *Data Race* (pelanggaran model memori C++) dan *Race Condition* (anomali logika konkuren).
- [ ] Dampak invokasi destruktor `std::thread` yang masih berstatus `joinable()` serta keuntungan transisi ke `std::jthread`.
- [ ] Penyebab teknis terjadinya *spurious wakeup* pada subsistem kernel dan pola penggunaan predikat pada `std::condition_variable`.
- [ ] Enam model konsistensi memori di C++: `memory_order_relaxed`, `consume`, `acquire`, `release`, `acq_rel`, dan `seq_cst`.
- [ ] Fenomena *False Sharing*, batas ukuran arsitektur *cache line*, dan teknik pencegahan menggunakan `alignas`.
- [ ] Mekanisme kerja operasi CAS (*Compare-And-Swap*) melalui `atomic::compare_exchange_weak` vs `compare_exchange_strong`.
- [ ] Bahaya antipattern *Double-Checked Locking* tanpa operasi atomik terpagar (*memory barriers*) pada arsitektur *weakly-ordered*.
- [ ] Cara kerja RAII wrapper sinkronisasi: `std::lock_guard`, `std::unique_lock`, `std::shared_lock`, dan `std::scoped_lock`.

### Saya tidak perlu menghafal:
- [ ] Nilai numerik pasti dari *opcode assembly* instruksi atomik (seperti `MFENCE`, `LOCK CMPXCHG` pada x86 atau `DMB`, `LDREX/STREX` pada ARM).
- [ ] Nilai byte pasti dari `std::hardware_destructive_interference_size` pada setiap vendor prosesor (cukup gunakan konstanta standar STL).
- [ ] Seluruh implementasi spesifik *kernel syscall* futex Linux atau Windows wait primitives di balik layar abstraksi STL.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengeliminasi masalah *Data Race* serta *Deadlock* menggunakan alat kompilator dinamis (**ThreadSanitizer / TSan**).
- [ ] Merancang algoritma sinkronisasi bebas kunci (*lock-free*) menggunakan semantik *acquire-release* untuk pipeline throughput tinggi.
- [ ] Mencegah terjadinya *Deadlock* dengan menerapkan penguncian terurut konsisten (*lock ordering*) atau memanfaatkan `std::scoped_lock`.
- [ ] Mengimplementasikan *thread pool* berkinerja tinggi yang menangani propagasi exception secara benar ke calling thread via `std::future`.
- [ ] Mengukur dan mengoptimalkan performa program multithreaded dengan meminimalkan *cache line bouncing* dan *lock contention* menggunakan *hardware profiler* (seperti `perf` atau Intel VTune).