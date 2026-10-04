# MODUL PEMBELAJARAN: ADVANCED MODERN C++ CONCURRENCY & MULTITHREADING
**Kategori:** 02-Programming-Languages  
**Kurikulum:** C++ (C++20/C++23 Standard)  
**Bab/Modul:** Bab 07 Module 01 — *Concurrency, Multithreading & Memory Model Synchronization*

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** CPP-CONC-0701
* **Nama Modul:** Concurrency Architecture, Thread Lifecycle Management, dan Primitive Synchronization
* **Tingkat Kesulitan:** Intermediate hingga Advanced
* **Prasyarat:** 
  * Penguasaan alokasi memori heap/stack dan pointer C++ (Bab 03)
  * Pemahaman mendalam tentang Resource Acquisition Is Initialization (RAII) dan Move Semantics (Bab 05)
  * Pemahaman dasar tentang arsitektur hardware Von Neumann, register CPU, dan Cache L1/L2/L3
* **Target Standar C++:** ISO/IEC 14882:2020 (C++20) & C++23 Extensions
* **Estimasi Waktu Selesai:** 8 - 12 Jam Studi Terfokus & Praktikum

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara komprehensif, peserta mampu:

1. **Menganalisis Arsitektur Eksekusi Konkuren:** Membedakan antara konkurensi logis (concurrency) dan paralelisme fisik (hardware parallelism) serta interaksinya dengan Thread Control Block (TCB) pada level kernel OS.
2. **Mengelola Siklus Hidup Thread secara Deterministik:** Mengimplementasikan siklus hidup thread berbasis RAII menggunakan `std::jthread`, token pembatalan kooperatif (`std::stop_token`), dan mencegah invokasi `std::terminate()` akibat thread yang *joinable*.
3. **Mencegah Kerusakan State (Data Races):** Mengeliminasi Data Race dan mendiagnosis Race Conditions menggunakan sinkronisasi mutual exclusion (`std::mutex`, `std::shared_mutex`, `std::recursive_mutex`) dan RAII lock wrappers (`std::unique_lock`, `std::shared_lock`, `std::scoped_lock`).
4. **Membangun Komunikasi Antar-Thread Bebas Spurious Wakeup:** Mengkonstruksi mekanisme koordinasi produsen-konsumen deterministik berbasis `std::condition_variable` dan `std::condition_variable_any` dengan predikat boolean eksplisit.
5. **Memahami Memory Model C++ dan Tingkat Reordering:** Menjelaskan fenomena kompilator dan prosesor dalam melakukan *instruction reordering*, implikasi cache coherence (protokol MESI/MOESI), dan dasar atomic orderings (`seq_cst`, `acquire-release`, `relaxed`).
6. **Menerapkan Profiling dan Sanitasi Multithread:** Mengintegrasikan ThreadSanitizer (TSan) dan profiler konkurensi untuk mendeteksi *deadlock*, *lock contention*, dan *false sharing*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam pemrograman sekuensial (single-threaded), model mental pengembang bersandar pada ilusi **Deterministic Serial Consistency**: Instruksi dieksekusi dari atas ke bawah, baris demi baris, dan memori adalah papan tulis pasif yang mempertahankan nilai terakhir yang ditulis.

```
Model Mental Sekuensial (Salah untuk Multithreading):
Thread 1:  [ Tulis A = 1 ] ───> [ Tulis B = 2 ] ───> [ Baca A (Pasti 1) ]
```

Dalam pemrograman konkuren dan paralel modern, ilusi tersebut hancur oleh tiga layer abstraksi:
1. **Kompilator yang Agresif:** Kompilator berhak mengubah urutan instruksi (*instruction reordering*) atau menghapus operasi memori jika menurut analisis *as-if rule*, eksekusi single-thread tidak terpengaruh.
2. **Out-of-Order CPU Architecture:** CPU modern memiliki store buffer, invalidation queues, dan pipeline eksekusi spekulatif. CPU mengeksekusi instruksi begitu dependensi operan terpenuhi, bukan berdasarkan nomor baris source code Anda.
3. **Hirarki Cache Multilevel (L1/L2/L3):** Setiap CPU Core memiliki cache L1/L2 privat. Nilai yang ditulis Core 1 ke RAM tidak langsung terlihat oleh Core 2 tanpa koordinasi cache coherency bus yang disinkronisasi oleh memori barrier hardware.

**Mental Model yang Benar:** Anggap setiap thread sebagai pekerja otonom yang bekerja di kantor terpisah. Meja kerja mereka adalah cache lokal, dan gudang pusat adalah RAM utama. Mereka tidak pernah berkomunikasi secara instan kecuali Anda memasang protokol legal eksplisit: **Synchronization Primitives** (Mutex, Semaphore, Barrier) atau **Atomic Operations dengan Memory Ordering**.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Interaksi Thread, Mutex, OS Futex, dan Hirarki Memori

```
+-----------------------------------------------------------------------------------+
| USER SPACE                                                                        |
|                                                                                   |
|  +---------------------------+             +---------------------------+          |
|  | Thread 1 (Core 0)         |             | Thread 2 (Core 1)         |          |
|  | - std::jthread worker1    |             | - std::jthread worker2    |          |
|  | - Local Stack Variables   |             | - Local Stack Variables   |          |
|  +-------------+-------------+             +-------------+-------------+          |
|                |                                         |                        |
|                | std::scoped_lock(mtx)                   | std::scoped_lock(mtx)  |
|                v                                         v                        |
|   +----------------------------+            +----------------------------+        |
|   | Fast Path: User-space test |            | Fast Path: Atomic CAS fail |        |
|   | (Atomic CAS 0 -> 1 SUKSES) |            | (Kontensi Terdeteksi!)     |        |
|   +--------------+-------------+            +--------------+-------------+        |
|                  |                                         |                      |
+------------------|-----------------------------------------|----------------------+
| KERNEL SPACE     |                                         v                      |
|                  |                         +-----------------------------------+  |
|                  |                         | Slow Path: Syscall sys_futex()    |  |
|                  |                         | Put Thread 2 to SLEEP / BLOCKED   |  |
|                  |                         | Enqueue to Mutex Wait Queue       |  |
|                  |                         +-----------------+-----------------+  |
|                  |                                           ^                    |
|                  | Lock Release & Futex Wake                 |                    |
|                  +-------------------------------------------+                    |
+-----------------------------------------------------------------------------------+
| HARDWARE & CACHE ARCHITECTURE                                                     |
|                                                                                   |
|   [ CPU Core 0 ]                             [ CPU Core 1 ]                       |
|   +-----------------------+                  +-----------------------+            |
|   | L1/L2 Cache (Modified)|                  | L1/L2 Cache (Shared/I)|            |
|   +-----------+-----------+                  +-----------+-----------+            |
|               |                                          |                        |
|               +--------------------+---------------------+                        |
|                                    | Interconnect Bus (MESI Coherency)            |
|                                    v                                              |
|                      +---------------------------+                                |
|                      | Shared L3 Cache           |                                |
|                      +-------------+-------------+                                |
|                                    |                                              |
|                                    v                                              |
|                      +---------------------------+                                |
|                      | Shared Main Memory (RAM)  |                                |
|                      +---------------------------+                                |
+-----------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Thread Control Block (TCB) dan Stack Space
Ketika `std::thread` atau `std::jthread` diinstansiasi, runtime C++ (melalui `pthread_create` di Linux/POSIX atau `CreateThread` di Win32) mengalokasikan:
* **Thread Stack:** Default 2MB hingga 8MB per thread (tergantung sistem operasi) untuk local variables, return addresses, dan frame pointers.
* **Thread Local Storage (TLS):** Blok data independen untuk variabel bertipe `thread_local`.
* **Kernel TCB:** Struktur data dalam ring 0 yang memegang state register CPU (Program Counter, Stack Pointer, General Purpose Registers), scheduling priority, dan thread ID.

### 2. Anatomi Internal `std::mutex` dan Konsep Futex
`std::mutex` modern tidak langsung melakukan transisi ke kernel space (syscall) yang memakan ratusan siklus CPU. Implementasinya berbasis **Hybrid Mutex** (pada Linux berbasis `futex` — *Fast Userspace Mutex*):
1. **Fast-path (Userspace):** Menggunakan instruksi CPU atomic *Compare-And-Swap* (CAS). Jika state mutex adalah `0` (unlocked), thread mengubahnya menjadi `1` secara atomic di userspace tanpa melibatkan kernel. Biaya: ~10-25 nanodetik.
2. **Slow-path (Kernel transition):** Jika kontensi terjadi (state sudah `1`), thread memanggil syscall `futex(..., FUTEX_WAIT, ...)`. Kernel menangguhkan thread (*context switch*) dan memasukkannya ke antrean tunggu sleep-state. Thread tidak membuang clock cycle CPU untuk *busy-waiting*.
3. **Unlock:** Thread pelepas melakukan atomic decrement. Jika ada waiter, kernel dipanggil via `futex(..., FUTEX_WAKE, ...)` untuk membangunkan satu atau semua thread dari antrean.

### 3. Protokol Cache Coherency (MESI)
Hardware multiprocessor menjaga konsistensi data di multi-cache melalui protokol MESI:
* **Modified (M):** Cache line hanya ada di cache lokal saat ini dan kotor (*dirty*), belum ditulis ke RAM.
* **Exclusive (E):** Cache line bersih, identik dengan RAM, dan hanya ada di cache saat ini.
* **Shared (S):** Cache line bersih, ada di beberapa cache Core secara simultan (operasi Read aman tanpa bus-lock).
* **Invalid (I):** Cache line tidak valid; pembacaan harus membaca ulang dari L3 atau RAM.

Saat dua thread pada Core berbeda memodifikasi variabel bersebelahan dalam cache line yang sama (biasanya 64 byte), fenomena **False Sharing** terjadi: baris cache berulang kali dibatalkan (*invalidated*) bolak-balik antar-core, meruntuhkan throughput memori hingga 95%.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Data Race vs Race Condition
* **Data Race (UB — Undefined Behavior):** Terjadi ketika minimal dua thread mengakses lokasi memori yang sama secara simultan, setidaknya satu akses adalah operasi *Write*, dan tidak ada sinkronisasi mutual exclusion atau atomic operation. Data race di C++ merusak optimasi kompilator dan menghasilkan *undefined behavior* absolut.
* **Race Condition (Bug Logika):** Terjadi ketika urutan eksekusi thread memengaruhi kebenaran (*correctness*) logika program, meskipun semua akses memori secara teknis terlindungi oleh mutex dan tidak mengandung *data race*.

### 2. Deadlock dan 4 Kondisi Coffman
Deadlock adalah kondisi di mana dua atau lebih thread terhenti selamanya karena saling menunggu resource yang dipegang oleh thread lain. Deadlock terjadi jika dan hanya jika keempat kondisi Coffman terpenuhi secara simultan:
1. **Mutual Exclusion:** Resource tidak dapat dibagi (eksklusif untuk satu thread pada satu waktu).
2. **Hold and Wait:** Thread memegang resource sembari meminta resource baru yang sedang ditahan thread lain.
3. **No Preemption:** Resource hanya dapat dilepaskan secara sukarela oleh pemegangnya.
4. **Circular Wait:** Terdapat rantai melingkar: Thread $A$ menunggu resource yang ditahan Thread $B$, dan Thread $B$ menunggu resource yang ditahan Thread $A$.

*Mitigasi C++ Modern:* Menghilangkan *Circular Wait* menggunakan `std::scoped_lock` (C++17/C++20) yang menerapkan algoritma *deadlock avoidance* berbasis *deadlock-free resource acquisition algorithm* (mirip Banker's Algorithm atau deterministic address-ordered locking).

### 3. RAII Synchronizers: Membandingkan Lock Wrappers
* `std::lock_guard`: Lock wrapper ultra-ringan berbasis RAII. Mengunci pada konstruksi, membuka pada destruksi. Tidak dapat dibuka manual (*non-movable*, *non-copyable*).
* `std::unique_lock`: RAII wrapper fleksibel. Memiliki *ownership* eksklusif atas mutex, mendukung *deferred locking*, pelepasan manual sebelum keluar scope, dan dapat dipindahkan (*movable*). Wajib digunakan bersama `std::condition_variable`.
* `std::shared_lock`: Read-lock wrapper untuk `std::shared_mutex` (pola Readers-Writer Lock). Banyak thread pembaca dapat masuk serempak, namun penulis memblokir semua pembaca.
* `std::scoped_lock`: Mengunci sejumlah sembarang mutex secara atomic tanpa risiko deadlock.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL (Step-by-Step)

Program berikut mendemonstrasikan evolusi pengelolaan thread dan penguncian primitif: migrasi dari `std::thread` tradisional ke `std::jthread` (C++20), penggunaan `std::scoped_lock` untuk eliminasi deadlock, dan sinkronisasi produsen-konsumen via `std::condition_variable`.

```cpp
#include <iostream>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <queue>
#include <chrono>
#include <vector>
#include <stop_token>

class SynchronizedOutputQueue {
private:
    std::mutex mtx_;
    std::condition_variable cv_;
    std::queue<std::string> message_queue_;
    bool is_shutdown_{false};

public:
    void push(std::string msg) {
        {
            // RAII: Mengunci mutex secara aman
            std::lock_guard<std::mutex> lock(mtx_);
            message_queue_.push(std::move(msg));
        }
        // Notifikasi satu consumer yang menunggu di luar critical section
        cv_.notify_one();
    }

    void shutdown() {
        {
            std::lock_guard<std::mutex> lock(mtx_);
            is_shutdown_ = true;
        }
        // Bangunkan seluruh thread yang tertidur untuk exit-path
        cv_.notify_all();
    }

    bool pop(std::string& out_msg) {
        // std::unique_lock wajib untuk std::condition_variable
        std::unique_lock<std::mutex> lock(mtx_);

        // Predicate lambda untuk menangani Spurious Wakeup
        cv_.wait(lock, [this]() {
            return !message_queue_.empty() || is_shutdown_;
        });

        if (message_queue_.empty() && is_shutdown_) {
            return false; // Queue kosong dan sistem shutdown
        }

        out_msg = std::move(message_queue_.front());
        message_queue_.pop();
        return true;
    }
};

void dead_lock_prevention_demo() {
    std::mutex account_a_mtx;
    std::mutex account_b_mtx;

    // Skenario: Transfer dana dua arah serempak
    auto transfer = [](std::mutex& m1, std::mutex& m2, const std::string& thread_name) {
        // C++17/C++20 std::scoped_lock mengunci multi-mutex tanpa deadlock!
        std::scoped_lock lock(m1, m2);
        std::cout << "[" << thread_name << "] Berhasil mengunci kedua mutex secara aman!\n";
    };

    std::jthread t1(transfer, std::ref(account_a_mtx), std::ref(account_b_mtx), "Thread-1 (A->B)");
    std::jthread t2(transfer, std::ref(account_b_mtx), std::ref(account_a_mtx), "Thread-2 (B->A)");

    // std::jthread otomatis melakukan join() pada akhir scope destructor
}

int main() {
    std::cout << "=== DEMO 1: DEADLOCK PREVENTION VIA SCOPED_LOCK ===\n";
    dead_lock_prevention_demo();

    std::cout << "\n=== DEMO 2: PRODUCER-CONSUMER WITH JTHREAD & CV ===\n";
    SynchronizedOutputQueue queue;

    // Consumer Thread menggunakan C++20 std::jthread
    std::jthread consumer([&queue](std::stop_token st) {
        std::string item;
        while (!st.stop_requested()) {
            if (queue.pop(item)) {
                std::cout << "[Consumer] Processed: " << item << "\n";
            } else {
                break; // Pipeline shutdown
            }
        }
        std::cout << "[Consumer] Shutdown complete.\n";
    });

    // Producer logic
    for (int i = 1; i <= 5; ++i) {
        queue.push("Telemetry Payload #" + std::to_string(i));
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    queue.shutdown();
    // Consumer otomatis di-join saat instance 'consumer' out-of-scope di sini.
    return 0;
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* `class SynchronizedOutputQueue`: Membungkus container non-thread-safe (`std::queue`) ke dalam abstraksi monitor thread-safe.
* `std::lock_guard<std::mutex> lock(mtx_);` (Metode `push`): Mengunci `mtx_` menggunakan idiom RAII. Jika exception dilempar, lock dijamin dilepas otomatis saat stack unwind.
* `cv_.notify_one();` (Metode `push`): Dipanggil di luar kurung kurawal critical section untuk mencegah fenomena *pessimization* (thread terbangun langsung membentur mutex yang masih terkunci).
* `std::unique_lock<std::mutex> lock(mtx_);` (Metode `pop`): `condition_variable` memerlukan kemampuan melepas lock saat masuk *sleep state* dan memperolehnya kembali saat terbangun. Mutex tidak bisa dimanipulasi dengan `lock_guard` untuk fungsi ini.
* `cv_.wait(lock, [this]() { return !message_queue_.empty() || is_shutdown_; });`: **Esensial!** Menerapkan predikat eksplisit. Mengeliminasi **Spurious Wakeup** (interupsi OS yang membangunkan thread tanpa ada sinyal notification aktual).
* `std::scoped_lock lock(m1, m2);`: Menerapkan algoritma deadlock-avoidance variadic template. Memastikan urutan penguncian internal konsisten secara global terlepas dari urutan parameter argumen.
* `std::jthread`: Standard threading class C++20. Berbeda dengan `std::thread`, `std::jthread` secara otomatis memanggil `request_stop()` dan `join()` pada destruktornya. Menghilangkan risiko fatal pemanggilan `std::terminate()`.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Konteks: High-Throughput Financial Order-Matching Engine Telemetry
Dalam sistem high-frequency trading (HFT) atau bursa kripto, modul telemetry harus mencatat puluhan ribu transaksi per detik ke disk/network tanpa memblokir thread eksekusi utama (*trading matching loop*).

### Masalah:
Pencatatan langsung (synchronous logging/disk I/O) dalam matching loop menyebabkan spike latensi (jitter) drastis dari 800 nanodetik menjadi 5 milidetik akibat flushing kernel page-cache.

### Solusi Arsitektural:
Implementasikan **Lock-Free/Low-Contention Bounded Asynchronous Ring-Buffer Logging System** berbasis worker thread background. Matching engine hanya melakukan copy memory berkecepatan tinggi ke bounded buffer thread-safe. Jika buffer penuh, strategi backpressure deterministic diterapkan. Worker thread backend bertugas mem-flush batch order records ke storage.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Sistem ini adalah pipeline Telemetry Asinkron berkinerja tinggi, thread-safe, dan *production-ready* menggunakan C++20.

```cpp
#include <iostream>
#include <vector>
#include <queue>
#include <string>
#include <mutex>
#include <condition_variable>
#include <thread>
#include <chrono>
#include <memory>
#include <sstream>

struct ExecutionReport {
    uint64_t order_id;
    char symbol[8];
    double price;
    uint32_t quantity;
    uint64_t timestamp_ns;
};

class ProductionTelemetrySink {
public:
    explicit ProductionTelemetrySink(size_t max_capacity = 10000)
        : max_capacity_(max_capacity) 
    {
        // Jalankan background worker
        worker_ = std::jthread([this](std::stop_token st) { 
            worker_loop(st); 
        });
    }

    ~ProductionTelemetrySink() {
        // Shutdown kooperatif dan deterministik
        stop_source_.request_stop();
        {
            std::lock_guard<std::mutex> lock(queue_mtx_);
            cv_drain_.notify_all();
        }
        // worker_ jthread akan otomatis me-request stop dan join di sini
    }

    ProductionTelemetrySink(const ProductionTelemetrySink&) = delete;
    ProductionTelemetrySink& operator=(const ProductionTelemetrySink&) = delete;

    bool submit_record(ExecutionReport report) {
        {
            std::lock_guard<std::mutex> lock(queue_mtx_);
            if (buffer_.size() >= max_capacity_) {
                // Backpressure: drop record atau return false untuk alert trading engine
                dropped_events_++;
                return false;
            }
            buffer_.push(report);
        }
        cv_drain_.notify_one();
        return true;
    }

    size_t get_dropped_count() const {
        return dropped_events_.load(std::memory_order_relaxed);
    }

private:
    void worker_loop(std::stop_token st) {
        std::vector<ExecutionReport> batch;
        batch.reserve(512);

        while (!st.stop_requested()) {
            {
                std::unique_lock<std::mutex> lock(queue_mtx_);
                
                // Tunggu sampai ada data ATAU terjadi request stop
                cv_drain_.wait_for(lock, std::chrono::milliseconds(10), [this, &st]() {
                    return !buffer_.empty() || st.stop_requested();
                });

                // Batch drain pattern: Pindahkan seluruh queue ke lokal
                // untuk meminimalkan durasi penahanan lock (Critical Section Minimalization)
                while (!buffer_.empty() && batch.size() < 512) {
                    batch.push_back(buffer_.front());
                    buffer_.pop();
                }
            } // Lock otomatis dilepas di sini!

            if (!batch.empty()) {
                flush_to_underlying_media(batch);
                batch.clear();
            }
        }

        // Drain sisa data sebelum thread benar-benar mati
        drain_remaining();
    }

    void flush_to_underlying_media(const std::vector<ExecutionReport>& batch) {
        // Simulasi penulisan hardware (Disk I/O / Socket)
        // Di sini sama sekali TIDAK ADA penguncian mutex queue_mtx_!
        std::ostringstream ss;
        for (const auto& r : batch) {
            ss << "[SINK-FLUSH] OrderID: " << r.order_id 
               << " | Price: " << r.price 
               << " | Qty: " << r.quantity << "\n";
        }
        std::cout << ss.str();
    }

    void drain_remaining() {
        std::lock_guard<std::mutex> lock(queue_mtx_);
        while (!buffer_.empty()) {
            const auto& r = buffer_.front();
            std::cout << "[FINAL-DRAIN] OrderID: " << r.order_id << "\n";
            buffer_.pop();
        }
    }

    const size_t max_capacity_;
    std::queue<ExecutionReport> buffer_;
    mutable std::mutex queue_mtx_;
    std::condition_variable cv_drain_;
    std::atomic<size_t> dropped_events_{0};
    std::stop_source stop_source_;
    std::jthread worker_;
};

int main() {
    std::cout << "Memulai Production Telemetry System Pipeline...\n";
    ProductionTelemetrySink sink(5000);

    // Simulasi 4 Matching Engine Threads yang memuntahkan report secara masif
    std::vector<std::jthread> matching_cores;
    for (int core_id = 0; core_id < 4; ++core_id) {
        matching_cores.emplace_back([&sink, core_id]() {
            for (int i = 0; i < 50; ++i) {
                ExecutionReport r{
                    .order_id = static_cast<uint64_t>(core_id * 1000 + i),
                    .symbol = "BTCUSDT",
                    .price = 65000.0 + (i * 1.5),
                    .quantity = 2,
                    .timestamp_ns = 1700000000ULL + i
                };
                sink.submit_record(r);
                std::this_thread::sleep_for(std::chrono::microseconds(200));
            }
        });
    }

    // Tunggu semua thread trading core selesai
    matching_cores.clear(); 
    
    std::cout << "Semua Matching Engine Threads selesai. Menunggu Sink shutdown...\n";
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    return 0;
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Mekanisme Sinkronisasi | Throughput (Ops/sec) | CPU Overhead | Latensi | Skenario Penggunaan Terbaik |
| :--- | :--- | :--- | :--- | :--- |
| **`std::mutex` (via `std::scoped_lock`)** | Sedang-Tinggi (~10-40M) | Rendah saat tanpa kontensi; Sedang saat ada wait-queue | Rendah (~20ns userspace, ~3µs saat sleep syscall) | Proteksi data struktur umum, kompleksitas menengah, alur kritis pendek. |
| **`std::shared_mutex` (RWLock)** | Sangat Tinggi (Read), Buruk (Write) | Tinggi (Cache coherence bus validation meningkat) | Rendah (Read), Tinggi (Write Starvation) | Read-heavy system (>95% Read, <5% Write), seperti Cache In-Memory Config. |
| **Spinlock (`atomic_flag`)** | Ekstrem Tinggi (jika tanpa kontensi) | Sangat Tinggi (100% CPU core spinning saat kontensi) | Sub-nanodetik (<5ns) | Konteks Real-Time/Kernel di mana thread dilarang sleep dan durasi lock < 50ns. |
| **Lock-Free Atomic (`std::atomic`)** | Paling Tinggi | Sangat Rendah | Minimal (Hardware Level instruction: `LOCK CMPXCHG`) | Counter, pointer-swapping, Single-Producer Single-Consumer (SPSC) queue. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Spurious Wakeups pada `std::condition_variable`
Sistem operasi POSIX dan Windows dapat membangunkan thread yang menunggu di condition variable tanpa alasan yang dipicu oleh kode aplikasi (misalnya karena interupsi sinyal kernel OS).
* **Konsekuensi:** Jika kode Anda membaca state tanpa pengecekan predikat:
  ```cpp
  // CRITICAL BUG! JANGAN LAKUKAN INI:
  cv.wait(lock);
  auto item = queue.front(); // CRASH! Queue mungkin masih kosong!
  ```
* **Solusi Wajib:** Selalu sertakan loop predikat atau lambda predikat:
  ```cpp
  cv.wait(lock, [&queue]() { return !queue.empty(); });
  ```

### 2. Thread Destruction Tanpa Join atau Detach
Jika objek `std::thread` dihancurkan saat masih berstatus `joinable() == true`, destruktornya **wajib** memanggil `std::terminate()`, yang langsung mematikan aplikasi seketika tanpa stack unwinding atau eksekusi destruktor RAII lainnya!
* **Solusi:** Selalu gunakan `std::jthread` (C++20).

### 3. Priority Inversion
Terjadi ketika thread berprioritas rendah memegang mutex, thread berprioritas tinggi membutuhkan mutex tersebut, namun thread berprioritas menengah terus menyita CPU karena scheduling preemptive, menghalangi thread berprioritas rendah melepaskan lock.
* **Solusi:** Gunakan priority inheritance protocol pada thread scheduler OS atau minimalkan lock retention time.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mempertahankan Lock Saat Melakukan Operasi I/O atau Network
```cpp
// KESALAHAN FATAL (Contention Hell):
void log_data(const std::string& data) {
    std::lock_guard<std::mutex> lock(global_mtx);
    // Operasi File I/O lambat berada di dalam Lock!
    file_stream << data << std::endl; 
}

// PERBAIKAN:
void log_data(const std::string& data) {
    std::string local_copy;
    {
        std::lock_guard<std::mutex> lock(global_mtx);
        // Salin data cepat di memori, lepas lock secepat mungkin!
        local_copy = data; 
    }
    // Lakukan I/O di luar critical section
    file_stream << local_copy << std::endl;
}
```

### 2. Penguncian Bertingkat dengan Urutan Berbeda (Deadlock Trap)
```cpp
// Thread 1
std::unique_lock lk1(mutexA);
std::unique_lock lk2(mutexB);

// Thread 2
std::unique_lock lk2(mutexB); // Potensi circular wait deadlock!
std::unique_lock lk1(mutexA);

// PERBAIKAN (C++17/C++20):
std::scoped_lock lock(mutexA, mutexB); // Dijamin bebas deadlock!
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Prinsip RAII Mutlak:** Jangan pernah memanggil `.lock()` dan `.unlock()` secara manual pada instance `std::mutex`. Selalu gunakan `std::scoped_lock`, `std::unique_lock`, atau `std::lock_guard`.
2. **Deklarasikan Mutex Dekat dengan Data yang Dilindungi:** Kelompokkan mutex dan data dalam satu struct/class. Jangan gunakan global mutex serbaguna.
   ```cpp
   struct Account {
       mutable std::mutex mtx;
       double balance [[guarded_by(mtx)]]; // Clang Thread Safety Annotation
   };
   ```
3. **Immutability First:** Data yang bersifat *Read-Only* tidak memerlukan sinkronisasi. Gunakan kata kunci `const` secara ketat. Objek yang immutable secara inheren adalah *thread-safe*.
4. **Adopsi `std::jthread` Secara Penuh (C++20):** Tinggalkan `std::thread` untuk kode baru guna mencegah unhandled `std::terminate()` dan memanfaatkan token kooperatif pembatalan.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Eliminasi False Sharing dengan Cache-Line Alignment
Ketika dua variabel dimodifikasi secara intensif oleh thread terpisah, pastikan keduanya tidak berada di dalam satu cache line (biasanya 64 bytes) menggunakan atribut alignas C++17 `hardware_destructive_interference_size`:

```cpp
#include <new>

struct ThreadMetrics {
    // Diposisikan pada cache line Core 0
    alignas(std::hardware_destructive_interference_size) std::atomic<uint64_t> core0_packets;

    // Dijamin berada di cache line BERBEDA dari core0_packets
    alignas(std::hardware_destructive_interference_size) std::atomic<uint64_t> core1_packets;
};
```
*Dampak:* Mengeliminasi serialisasi bus hardware cache, meningkatkan throughput hingga $10\times$ pada beban concurrent multithreaded write intensif.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Deadlock Denial of Service (DoS):** Pada sistem server, deadlock pada modul autentikasi atau connection handling menghentikan seluruh layanan. Pasang timeout penguncian menggunakan `std::timed_mutex` dan `std::unique_lock::try_lock_for()` pada layer arsitektur kritis:
   ```cpp
   std::unique_lock<std::timed_mutex> lock(timed_mtx, std::chrono::seconds(2));
   if (!lock.owns_lock()) {
       // Log security alert, mitigasi resource leak, dan tolak request graceful
       throw std::runtime_error("Lock acquisition timeout: Potensi Deadlock!");
   }
   ```
2. **Time-Of-Check to Time-Of-Use (TOCTOU) Flaws:**
   ```cpp
   // VULNERABLE:
   if (shared_map.contains(key)) { // Time of Check
       // Thread lain bisa menghapus key di sini!
       shared_map[key].process();  // Time of Use -> CRASH!
   }

   // SECURE:
   {
       std::scoped_lock lock(map_mtx);
       auto it = shared_map.find(key);
       if (it != shared_map.end()) {
           it->second.process();
       }
   }
   ```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Deteksi Data Race dengan ThreadSanitizer (TSan)
Kompilasikan program dengan flag instrumen TSan pada Clang/GCC:
```bash
clang++ -std=c++20 -fsanitize=thread -O1 -g code.cpp -o app_sanitized
./app_sanitized
```
TSan akan memotong runtime memori dan mengeluarkan laporan rinci (Call Stack, Thread ID, Instruction Address) saat operasi Data Race terjadi sekecil apa pun.

### 2. Penamaan Thread Native untuk Debugger (GDB/LLDB)
Identifikasi thread saat membaca stack trace di GDB:
```cpp
#include <pthread.h>

void name_thread(std::thread& th, const std::string& name) {
    auto handle = th.native_handle();
    pthread_setname_np(handle, name.substr(0, 15).c_str());
}
```
Di GDB, perintah `info threads` sekarang menampilkan label thread manusiawi:
```text
  Id   Target Id                  Name
* 1    Thread 0x7ffff7d92740 (LWP 4021) "MainEngine"
  2    Thread 0x7ffff7591640 (LWP 4022) "TelemetrySink"
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Pilih `std::jthread`:** Membatalkan otomatis (`stop_token`) dan bergabung otomatis (`join`) pada destruksi.
* **Pilih `std::scoped_lock`:** Solusi default untuk mengunci satu atau lebih dari satu mutex.
* **Pilih `std::unique_lock`:** Hanya gunakan saat membutuhkan fitur deferred-locking atau integrasi dengan `std::condition_variable`.
* **Kaidah Condition Variable:**
  1. Selalu modifikasi predikat di dalam lock.
  2. Selalu cek predikat menggunakan loop/lambda saat memanggil `wait`.
  3. Lakukan `notify_one()` / `notify_all()` setelah melepas lock jika memungkinkan kinerja tinggi.
* **C++ Memory Ordering Default:** Semua operasi primitif sinkronisasi tingkat tinggi dijamin memiliki semantik Sequential Consistency (`std::memory_order_seq_cst`).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Basic (1-5)

1. **Apa perbedaan perilaku paling mendasar antara destruktor `std::thread` dan destruktor `std::jthread` jika thread masih dalam keadaan *joinable*?**
   * *Jawaban:* Destruktor `std::thread` akan langsung memanggil `std::terminate()` dan menghentikan seluruh program secara abnormal. Destruktor `std::jthread` akan otomatis mengirimkan sinyal pembatalan kooperatif (`request_stop()`) dan mengeksekusi blocking `join()`, menyelesaikan eksekusi secara aman.

2. **Mengapa pemanggilan `std::mutex::lock()` dan `unlock()` secara manual dianggap sebagai anti-pattern di C++ modern?**
   * *Jawaban:* Karena tidak exception-safe. Jika baris kode di antara `lock()` dan `unlock()` melempar eksepsi (*exception*), alur program melompat ke blok handler tanpa mengeksekusi `unlock()`. Hal ini menyebabkan mutex terkunci permanen (*deadlock* pada thread lain yang mencoba mengaksesnya).

3. **Apakah fungsi dari lambda predikat pada pemanggilan `condition_variable::wait(lock, Predicate)`?**
   * *Jawaban:* Untuk mengatasi *spurious wakeup*. Predikat memeriksa ulang kondisi boolean logis aktual; jika thread dibangunkan secara salah oleh OS tanpa adanya data, predikat bernilai false dan thread secara otomatis kembali tidur.

4. **Mengapa `std::unique_lock` wajib digunakan bersama `std::condition_variable`, bukan `std::lock_guard`?**
   * *Jawaban:* Karena mekanisme internal `wait()` harus dapat membuka kunci mutex secara atomik saat thread mulai tidur, dan harus dapat mengunci kembali mutex tersebut secara otomatis begitu thread terbangun. `std::lock_guard` tidak memiliki interface dinamis untuk unlock/relock.

5. **Apa yang dimaksud dengan Data Race dalam spesifikasi standar C++?**
   * *Jawaban:* Situasi di mana dua thread mengakses alamat memori yang sama secara paralel tanpa sinkronisasi, di mana minimal salah satu thread melakukan modifikasi (*write*). Data race memicu *Undefined Behavior* (UB).

---

### Soal Tingkat Intermediate (6-10)

6. **Bagaimana `std::scoped_lock` (C++17) berhasil mencegah deadlock saat mengunci beberapa mutex sekaligus dibandingkan jika programmer menulis beberapa `std::lock_guard` berturutan?**
   * *Jawaban:* `std::scoped_lock` menggunakan algoritma *deadlock-avoidance* (seperti algoritma penguncian urutan alamat atau strategi try-lock bertingkat). Ini menjamin bahwa semua mutex diperoleh secara serentak tanpa peduli urutan parameter, menghilangkan kondisi *Circular Wait* dari Coffman.

7. **Jelaskan fenomena *False Sharing* pada CPU multicore dan dampaknya terhadap program multithreaded!**
   * *Jawaban:* Terjadi ketika dua core memodifikasi variabel independen yang secara fisik berada dalam satu cache line memori yang sama (64 byte). Protokol MESI hardware memaksa invalidasi bolak-balik seluruh cache line di antara kedua core, menyebabkan lonjakan bus traffic dan penurunan drastis performa memory access.

8. **Kapan Anda memilih menggunakan `std::shared_mutex` dibandingkan `std::mutex` biasa, dan kapan `std::shared_mutex` justru menurunkan performa?**
   * *Jawaban:* Tepat digunakan pada skenario pembacaan dominan (*read-heavy* >90%) dengan operasi penulisan yang sangat jarang. Penggunaan `std::shared_mutex` justru meruntuhkan performa jika operasi penulisan sering terjadi (*write-heavy*), karena overhead sinkronisasi internal atomic read-counter pada `shared_mutex` jauh lebih mahal daripada satu mutex biner sederhana.

9. **Apa bahayanya memanggil fungsi callback eksternal atau virtual method saat masih memegang `std::mutex`?**
   * *Jawaban:* Membuka celah deadlock fatal (*Deadlock by Reentrancy / Inversion*). Callback eksternal mungkin mencoba mengunci mutex yang sama dari thread yang sama (jika bukan recursive mutex) atau mencoba mengunci mutex lain yang sedang dipegang oleh thread berbeda yang juga menunggu mutex pertama.

10. **Bagaimana mekanisme internal cooperative cancellation pada `std::stop_token` dan `std::jthread` bekerja?**
    * *Jawaban:* `std::jthread` memegang `std::stop_source` internal. Ketika `request_stop()` dipanggil, shared-state internal atomic flag disetel ke true. Thread worker yang memegang `std::stop_token` dapat melakukan polling berkala menggunakan method `token.stop_requested()` atau mendaftarkan `std::stop_callback` untuk terminasi kooperatif tanpa menghentikan thread secara paksa (*non-preemptive*).

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Engine Thread Pool Berkinerja Tinggi C++20 dengan Dukungan Futures & Graceful Cancellation"

### Spesifikasi Teknis:
Bangun sebuah class `ThreadPool` C++20 fungsional dengan spesifikasi berikut:
1. **Inisialisasi Dinamis:** Menerima argumen jumlah thread pekerja (default: `std::thread::hardware_concurrency()`) yang disimpan dalam `std::vector<std::jthread>`.
2. **Generic Task Enqueueing:** Implementasikan fungsi template:
   ```cpp
   template<typename F, typename... Args>
   auto submit(F&& f, Args&&... args) 
       -> std::future<std::invoke_result_t<F, Args...>>;
   ```
   Fungsi ini harus membungkus task ke dalam `std::packaged_task` dan mengembalikan `std::future` ke pemanggil.
3. **Penyimpanan Task Aman:** Antrean tugas bertipe `std::queue<std::move_only_function<void()>>` (C++23) atau `std::queue<std::function<void()>>` yang dilindungi oleh `std::mutex` dan dikoordinasi dengan `std::condition_variable`.
4. **Shutdown Graceful & Instant:**
   * Method `drain_and_stop()`: Menyelesaikan semua sisa antrean sebelum shutdown.
   * Method `cancel_and_stop()`: Mengabaikan sisa antrean yang belum berjalan dan membatalkan worker secepat mungkin via `std::stop_token`.
5. **Verifikasi:** Uji program dengan memproses 1.000 komputasi intensif dan pastikan program bersih dari *Data Race* serta *Memory Leak* saat dianalisis menggunakan `-fsanitize=thread`.