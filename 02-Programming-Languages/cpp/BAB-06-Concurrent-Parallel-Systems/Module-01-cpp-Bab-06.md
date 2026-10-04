# Bab 06 Module 01: Concurrent & Parallel Systems

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Pemrograman Sistem & Bahasa Tingkat Rendah (`02-Programming-Languages`)
*   **Mata Pelajaran:** Rekayasa Sistem C++ Modern (Modern C++ System Engineering)
*   **Kode Modul:** CPP-SYS-0601
*   **Judul Modul:** Concurrent & Parallel Systems
*   **Tingkat Kesulitan:** Advanced / Lanjutan
*   **Prasyarat Konseptual:**
    *   Penguasaan Manajemen Memori C++ (Pointers, References, RAII, Stack vs Heap).
    *   Siklus Hidup Objek (Object Lifetime) dan Move Semantics (C++11/14/17).
    *   Arsitektur Komputer Dasar (Struktur CPU, Register, Cache L1/L2/L3, Virtual Memory).
*   **Estimasi Waktu Penyelesaian:** 12–16 Jam Pembelajaran Mandiri / Praktikum Terbimbing

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis dan Membedakan** secara matematis dan arsitektural antara konkurensi (*concurrency*) dan paralelisme (*parallelism*) dalam konteks eksekusi instruksi modern multi-core.
2.  **Mengoperasikan Primitif Thread Modern** (`std::thread`, `std::jthread`, `std::stop_token`) dengan jaminan *resource safety* berbasis RAII tanpa risiko *zombie thread* atau *unhandled termination*.
3.  **Mengimplementasikan Sinkronisasi Data Bebas Data Race** menggunakan `std::mutex`, `std::unique_lock`, `std::shared_mutex`, dan `std::condition_variable` sesuai *lock hierarchy* yang deterministik.
4.  **Menjelaskan Memory Model C++ (C++11 ke atas)** termasuk konsep *Happens-Before Relationship*, *Synchronizes-With*, serta aplikasi semantik *Memory Ordering* (`memory_order_relaxed`, `memory_order_acquire`, `memory_order_release`, `memory_order_seq_cst`).
5.  **Mendeteksi dan Memitigasi Degradasi Performa Level Perangkat Keras** seperti *Cache Thrashing*, *False Sharing*, dan *Lock Contention* menggunakan teknik *hardware destructive interference size alignment*.
6.  **Merancang dan Menguji Sistem Antrian Tugas Asinkron (Lock-Based & Lock-Free Thread Pool)** yang stabil untuk beban kerja produksi berkepadatan tinggi.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### 1. Ilusi Eksekusi Sekuensial
Dalam pemrograman *single-threaded*, Anda terbiasa dengan model komputasi von Neumann yang deterministik: instruksi dieksekusi berurutan sesuai urutan kode sumber (*program order*). Dalam sistem *multi-threaded*, ilusi ini runtuh. 

Kompilator (melalui optimasi seperti *loop unrolling*, *instruction reordering*, dan *register allocation*) serta perangkat keras CPU (melalui *Out-of-Order Execution* dan *Store Buffers*) secara aktif mengubah urutan eksekusi aktual selama hasil akhir pada *thread yang sama* tidak melanggar aturan kausalitas lokal (*as-if rule*). Namun, thread lain yang mengamati memori tersebut akan melihat mutasi data yang tampak tidak berurutan, tidak lengkap, atau bahkan korup jika tidak ada sinkronisasi formal.

### 2. The Shared-State Hazard Mindset
Alih-alih melihat thread sebagai "pekerja independen yang cepat", pandanglah thread sebagai agen independen yang berpotensi merusak integritas state memori bersama (*shared state*). Operasi `counter++` di level bahasa tingkat tinggi bukanlah satu instruksi atomik, melainkan tripartit instruksi mesin:
1. Membaca nilai dari memori ke register (`MOV`).
2. Menambahkan nilai register sebesar satu (`ADD`).
3. Menuliskan kembali nilai register ke memori (`MOV`).

Jika intervensi konteks (*context switch*) terjadi di antara langkah-langkah ini, sistem masuk ke dalam status *undefined behavior* secara logis. **Aturan Utama:** Kapan pun dua atau lebih thread mengakses lokasi memori yang sama secara simultan dan setidaknya satu thread melakukan operasi penulisan (*write*), Anda menghadapi **Data Race**, yang didefinisikan oleh Standar C++ sebagai **Undefined Behavior (UB)** mutlak.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Interaksi Thread, CPU Core, dan Hirarki Cache
Perhatikan bagaimana thread C++ dipetakan ke thread OS (1:1 model pada Linux/Windows) dan bagaimana mereka berinteraksi dengan hirarki memori perangkat keras:

```text
+-------------------------------------------------------------------------+
|                        APLIKASI C++ (USER SPACE)                        |
|   +--------------------------+           +--------------------------+   |
|   |      std::thread A       |           |      std::thread B       |   |
|   | (Mutasi Data: Variable X)|           | (Membaca Data: Variable X|   |
|   +------------+-------------+           +------------+-------------+   |
+----------------|--------------------------------------|-----------------+
                 | (1:1 Pthread / Win32 Thread)         |
+----------------v--------------------------------------v-----------------+
|                       KERNEL SPACE (OS SCHEDULER)                       |
+----------------+--------------------------------------+-----------------+
                 |                                      |
+----------------v--------------------------------------v-----------------+
|                    HARDWARE ARCHITECTURE (MULTI-CORE)                   |
|  +---------------------------+        +---------------------------+     |
|  |          CORE 0           |        |          CORE 1           |     |
|  |  +---------------------+  |        |  +---------------------+  |     |
|  |  | Store Buffer / Regs |  |        |  | Store Buffer / Regs |  |     |
|  |  +----------+----------+  |        |  +----------+----------+  |     |
|  |             |             |        |             |             |     |
|  |  +----------v----------+  |        |  +----------v----------+  |     |
|  |  |     L1 Data Cache   |  |        |  |     L1 Data Cache   |  |     |
|  |  |      [Line: 64B]    |  |        |  |      [Line: 64B]    |  |     |
|  |  +----------+----------+  |        |  +----------+----------+  |     |
|  |             |             |        |             |             |     |
|  |  +----------v----------+  |        |  +----------v----------+  |     |
|  |  |       L2 Cache      |  |        |  |       L2 Cache      |  |     |
|  |  +----------+----------+  |        |  +----------+----------+  |     |
|  +-------------|-------------+        +-------------|-------------+     |
|                |                                    |                   |
|                +-----------------+------------------+                   |
|                                  | (MESI Protocol Bus)                  |
|                 +----------------v----------------+                     |
|                 |     SHARED L3 CACHE (LLC)       |                     |
|                 +----------------+----------------+                     |
|                                  |                                      |
|                 +----------------v----------------+                     |
|                 |       MAIN MEMORY (DRAM)        |                     |
|                 +---------------------------------+                     |
+-------------------------------------------------------------------------+
```

### 2. Siklus Hidup dan Alur Koordinasi Thread (`std::condition_variable`)

```text
       PRODUCER THREAD                           CONSUMER THREAD
              |                                         |
     Lock unique_lock<mutex>                   Lock unique_lock<mutex>
              |                                         |
    Push Data ke Work Queue                             |
              |                                   Evaluasi Predikat:
     Unlock Mutex via RAII                       Is Queue Empty?
              |                                         |
       cv.notify_one()                        YES: cv.wait(lock)
              |                                [Atomically releases mutex
              |                                 & suspends thread execution]
              |                                         |
              +-------------- Signal ------------------>+
                                                        |
                                                [Wakes up, automatically
                                                 re-acquires mutex lock]
                                                        |
                                                  Re-check Predikat:
                                                  Is Queue Empty?
                                                        |
                                                 NO: Pop Task
                                                        |
                                                Manual / RAII Unlock Mutex
                                                        |
                                                Eksekusi Task
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Objek Thread C++
Pada platform Linux dengan glibc, sebuah `std::thread` secara internal membungkus representasi penanganan POSIX (`pthread_t`). Objek `std::thread` di sisi user-space hanyalah sebuah *handle* kecil (biasanya berukuran pointer 8-byte) yang mereferensikan *control block* di heap OS kernel:
*   **Thread Stack:** Dialokasikan oleh OS (default biasanya 2MB hingga 8MB) untuk call frame, variabel lokal, dan register context.
*   **TLS (Thread Local Storage):** Area memori independen untuk variabel berlabel `thread_local`.
*   **Thread State Block:** Berisi state thread (Running, Blocked, Ready, Terminated), salinan register CPU ($RIP, $RSP, register umum), dan bitmask sinyal.

### 2. Protokol Koherensi Cache (MESI Protocol)
CPU modern memastikan L1/L2 cache antar core tetap konsisten melalui protokol seperti MESI (*Modified, Exclusive, Shared, Invalid*):
*   **Modified (M):** Cache line hanya ada di cache lokal saat ini dan nilainya *dirty* (berbeda dari memori utama). Core ini memiliki izin eksklusif untuk menulis.
*   **Exclusive (E):** Cache line hanya ada di cache lokal saat ini dan *clean* (sama dengan memori utama).
*   **Shared (S):** Cache line ada di beberapa cache core secara paralel. Hanya diperbolehkan operasi baca (*read-only*).
*   **Invalid (I):** Cache line tidak lagi valid. Pembacaan harus mengambil ulang data dari bus/L3/RAM.

Ketika thread di Core 0 menulis ke variabel dalam cache line berstatus *Shared*, Core 0 memicu sinyal *Bus Invalidate*. Seluruh core lain yang memegang cache line tersebut dipaksa mengubah statusnya menjadi *Invalid*. Ini menjelaskan mengapa komputasi paralel yang memanipulasi memori bersebelahan secara agresif dapat mengalami degradasi kinerja drastis (*False Sharing*).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Concurrency vs Parallelism
*   **Concurrency (Konkurensi):** Komposisi independen dari proses/thread yang dieksekusi secara terpisah. Ini adalah persoalan *struktur* kode. Sistem konkuren menangani banyak hal sekaligus (*dealing with lots of things at once*) melalui pergantian konteks (*interleaving*) pada single core maupun multi-core.
*   **Parallelism (Paralelisme):** Eksekusi simultan dari beberapa komputasi pada core hardware yang terpisah secara fisik pada waktu instan $t$ yang sama. Ini adalah persoalan *eksekusi*. Paralelisme berfokus pada penyelesaian tugas lebih cepat dengan memecahnya ke beberapa unit komputasi (*doing lots of things at once*).

### 2. C++ Memory Model & Ordering Semantics
Standar C++11 memperkenalkan model memori formal yang mendefinisikan interaksi thread dengan hardware.

#### Operasi Atomik & Data Race
Operasi yang dibungkus oleh `std::atomic<T>` menjamin bahwa pembacaan atau penulisan data dilakukan tanpa fragmentasi byte (tidak ada fenomena *torn-read* atau *torn-write*).

#### Memory Ordering
C++ menyediakan 6 tingkatan *memory ordering* kontrol instruksi CPU:
1.  **`std::memory_order_relaxed`**: Hanya menjamin atomisitas modifikasi nilai. Tidak ada jaminan sinkronisasi urutan instruksi di luar variabel tersebut.
2.  **`std::memory_order_acquire`**: Digunakan pada operasi *read*. Mencegah instruksi pembacaan/penulisan setelahnya dalam program order dipindahkan ke *sebelum* operasi acquire ini.
3.  **`std::memory_order_release`**: Digunakan pada operasi *write*. Menjamin bahwa seluruh operasi pembacaan/penulisan sebelumnya telah diselesaikan dan dapat dilihat oleh thread lain yang melakukan *acquire* pada variabel atomic yang sama.
4.  **`std::memory_order_acq_rel`**: Kombinasi acquire dan release, umumnya untuk operasi *read-modify-write* (seperti `fetch_add`).
5.  **`std::memory_order_seq_cst`** (*Sequential Consistency*): Default pada `std::atomic`. Menjamin adanya urutan global tunggal yang disepakati oleh seluruh thread. Memiliki *overhead* performa tertinggi karena memerlukan CPU memory fence instruksional penuh (`MFENCE` / `DMB`).

```text
Thread 1 (Producer)                  Thread 2 (Consumer)
data = 42; --------------------+
atomic_flag.store(RELEASE);    | (Happens-Before Relationship)
                               |
                               +---> while(!atomic_flag.load(ACQUIRE));
                                     assert(data == 42); // Dijamin Valid!
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode dasar yang mengimplementasikan:
1. Penggunaan `std::jthread` (C++20) dengan cooperative cancellation via `std::stop_token`.
2. Sinkronisasi thread-safe counter menggunakan `std::mutex` dan `std::scoped_lock`.
3. Koordinasi Producer-Consumer menggunakan `std::condition_variable`.

```cpp
#include <iostream>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <queue>
#include <chrono>
#include <stop_token>

class SafeDataPipeline {
private:
    std::queue<int> buffer_;
    mutable std::mutex mtx_;
    std::condition_variable cv_;
    const size_t max_capacity_{5};

public:
    void produce(int value) {
        std::unique_lock<std::mutex> lock(mtx_);
        // Hindari Spurious Wakeups menggunakan predikat eksplisit
        cv_.wait(lock, [this]() { 
            return buffer_.size() < max_capacity_; 
        });

        buffer_.push(value);
        std::cout << "[Producer] Pushed: " << value 
                  << " | Queue Size: " << buffer_.size() << "\n";
        
        lock.unlock(); // Optimasi: lepaskan kunci sebelum notifikasi
        cv_.notify_one();
    }

    bool consume(int& out_value, std::stop_token st) {
        std::unique_lock<std::mutex> lock(mtx_);
        
        // Menunggu predikat atau adanya sinyal pembatalan stop_token
        while (buffer_.empty()) {
            if (st.stop_requested()) {
                return false;
            }
            // Tunggu dengan timeout interval pendek untuk memeriksa token
            cv_.wait_for(lock, std::chrono::milliseconds(100), [this]() {
                return !buffer_.empty();
            });
        }

        out_value = buffer_.front();
        buffer_.pop();
        std::cout << "[Consumer] Processed: " << out_value 
                  << " | Queue Size: " << buffer_.size() << "\n";

        lock.unlock();
        cv_.notify_one();
        return true;
    }
};

int main() {
    SafeDataPipeline pipeline;

    // C++20 std::jthread secara otomatis memanggil request_stop() dan join() saat destruct
    std::jthread consumer([&pipeline](std::stop_token st) {
        while (!st.stop_requested()) {
            int val = 0;
            if (pipeline.consume(val, st)) {
                std::this_thread::sleep_for(std::chrono::milliseconds(150));
            }
        }
        std::cout << "[Consumer] Stopped cooperatively.\n";
    });

    std::jthread producer([&pipeline]() {
        for (int i = 1; i <= 10; ++i) {
            pipeline.produce(i);
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
    });

    // Biarkan threads memproses data
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));

    std::cout << "[Main] Requesting worker cancellation...\n";
    consumer.request_stop();

    // producer dan consumer otomatis di-join di sini oleh destruktor std::jthread
    return 0;
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 7–10:** `std::queue<int> buffer_` berperan sebagai *shared mutable resource*. Objek ini diisolasi oleh `mtx_` dan disinkronkan oleh `cv_`. Mutex diberi flag `mutable` agar method *const-qualified* (misal: query `size()`) tetap dapat menguncinya.
*   **Baris 14:** `std::unique_lock<std::mutex> lock(mtx_);` mengakuisisi kepemilikan eksklusif atas mutex menggunakan prinsip RAII. Berbeda dengan `std::lock_guard`, `std::unique_lock` dapat di-unlock dan di-lock kembali secara eksplisit, yang merupakan kebutuhan mutlak bagi primitif `std::condition_variable`.
*   **Baris 16–18:** `cv_.wait(lock, Predicate)` mengevaluasi kondisi antrian. Mekanisme internalnya: jika predikat bernilai `false`, thread secara atomik melepaskan kepemilikan mutex dan menempatkan diri pada antrian tunggu OS (*wait queue*). Saat terbangun (karena sinyal notifikasi atau *spurious wakeup*), thread kembali mengakuisisi mutex sebelum mengevaluasi kembali predikat tersebut.
*   **Baris 24:** `lock.unlock(); cv_.notify_one();` membuka kunci sebelum memanggil notifikasi. Pola ini mencegah fenomena *pessimization wakeup* di mana thread consumer yang dibangunkan langsung terbentur (terblokir) kembali karena mutex masih ditahan oleh producer.
*   **Baris 28:** Penggunaan `std::stop_token` dari C++20. Menggantikan mekanisme interupsi manual menggunakan flag boolean yang rentan *race condition*.
*   **Baris 51:** Konstruktor `std::jthread` secara otomatis menginjeksi instance `std::stop_token` ke dalam signature fungsi target jika parameter pertama fungsi menerima tipe tersebut.
*   **Baris 72:** Destruktor `std::jthread` dipanggil secara otomatis saat keluar dari *scope main*. Destruktor ini mengeksekusi `request_stop()` dilanjutkan dengan pemanggilan `join()`, mengeliminasi bahaya `std::terminate` yang sering terjadi pada `std::thread` tradisional.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Engine Pemrosesan Transaksi Finansial Berfrekuensi Tinggi (HFT)
Sebuah bursa perdagangan komoditas memproses puluhan ribu instruksi order beli/jual per detik. Setiap paket order yang masuk melalui socket UDP/TCP kernel harus divalidasi, didekripsi, dialokasikan ke dalam antrian eksekusi, dan dipetakan ke buku order (*order book*).

### Masalah Arsitektur Lama
Implementasi awal menggunakan model *Thread-per-Connection*, di mana setiap koneksi klien memiliki thread eksklusif:
1.  **Overhead Context Switch:** OS menghabiskan lebih dari 40% siklus CPU hanya untuk melakukan pergantian status context switch thread kernel ($RSP, $RIP, TLB invalidation).
2.  **Thread Exhaustion:** Peningkatan jumlah koneksi konkuren memicu lonjakan penggunaan RAM akibat alokasi stack per-thread (8MB x 2000 thread = ~16GB overhead stack murni).
3.  **Lock Contention:** Banyak thread memperebutkan satu antrian order global yang dilindungi sebuah `std::mutex`, menyebabkan serialisasi sistem (Amdahl's Law bottleneck).

### Solusi Arsitektur Baru
Mengganti skema menjadi arsitektur berbasis **Fixed Worker Pool** dengan antrian kerja terpartisi (*Sharded Work-Stealing Thread Pool*), menggunakan alokasi memori yang disejajarkan dengan ukuran cache line (*Cache-line Aligned Data Structures*) untuk mengeliminasi false sharing.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA

Berikut adalah implementasi sistem antrian tugas multi-threaded (**Thread Pool**) tingkat produksi yang mendukung *future/promise completion token*, *thread safety*, dan penanganan *graceful degradation*.

```cpp
#include <iostream>
#include <vector>
#include <queue>
#include <memory>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <future>
#include <functional>
#include <stdexcept>
#include <new>

// Mengoptimalkan memory boundary untuk mencegah False Sharing
#if defined(__cpp_lib_hardware_interference_size)
    using std::hardware_destructive_interference_size;
#else
    // Default fallback 64 byte untuk arsitektur x86-64 / ARMv8 kontemporer
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

class ThreadPool {
public:
    explicit ThreadPool(size_t thread_count = std::thread::hardware_concurrency());
    
    // Non-copyable & Non-movable untuk integritas resource
    ThreadPool(const ThreadPool&) = delete;
    ThreadPool& operator=(const ThreadPool&) = delete;
    ThreadPool(ThreadPool&&) = delete;
    ThreadPool& operator=(ThreadPool&&) = delete;

    template<class F, class... Args>
    auto enqueue(F&& f, Args&&... args) 
        -> std::future<typename std::invoke_result<F, Args...>::type>;

    ~ThreadPool();

private:
    // Alokasi sebaris cache-line untuk mencegah False Sharing antar pool metadata
    alignas(hardware_destructive_interference_size) struct WorkerState {
        std::vector<std::thread> workers;
        std::queue<std::function<void()>> tasks;
        std::mutex queue_mutex;
        std::condition_variable cv;
        bool stop{false};
    } state_;
};

ThreadPool::ThreadPool(size_t thread_count) {
    if (thread_count == 0) {
        thread_count = 1; // Fallback jika detection hardware_concurrency gagal (return 0)
    }

    state_.workers.reserve(thread_count);
    for (size_t i = 0; i < thread_count; ++i) {
        state_.workers.emplace_back([this]() {
            while (true) {
                std::function<void()> task;
                {
                    std::unique_lock<std::mutex> lock(this->state_.queue_mutex);
                    this->state_.cv.wait(lock, [this]() {
                        return this->state_.stop || !this->state_.tasks.empty();
                    });

                    if (this->state_.stop && this->state_.tasks.empty()) {
                        return; // Terminasi worker secara bersih
                    }

                    task = std::move(this->state_.tasks.front());
                    this->state_.tasks.pop();
                }
                
                // Eksekusi task di luar critical section
                try {
                    task();
                } catch (const std::exception& e) {
                    std::cerr << "[ThreadPool Worker Error]: " << e.what() << "\n";
                } catch (...) {
                    std::cerr << "[ThreadPool Worker Error]: Fatal unknown exception caught\n";
                }
            }
        });
    }
}

template<class F, class... Args>
auto ThreadPool::enqueue(F&& f, Args&&... args) 
    -> std::future<typename std::invoke_result<F, Args...>::type> 
{
    using return_type = typename std::invoke_result<F, Args...>::type;

    // Membungkus callable object ke dalam std::packaged_task melalui heap-pointer (shared_ptr)
    auto task_pkg = std::make_shared<std::packaged_task<return_type()>>(
        std::bind(std::forward<F>(f), std::forward<Args>(args)...)
    );
    
    std::future<return_type> res = task_pkg->get_future();
    {
        std::unique_lock<std::mutex> lock(state_.queue_mutex);
        if (state_.stop) {
            throw std::runtime_error("Submission rejected: ThreadPool is shutting down.");
        }

        // Simpan wrapper lambda yang mengeksekusi packaged_task
        state_.tasks.emplace([task_pkg]() { 
            (*task_pkg)(); 
        });
    }
    state_.cv.notify_one();
    return res;
}

ThreadPool::~ThreadPool() {
    {
        std::unique_lock<std::mutex> lock(state_.queue_mutex);
        state_.stop = true;
    }
    
    state_.cv.notify_all(); // Bangunkan seluruh worker untuk proses flush akhir
    
    for (std::thread& worker : state_.workers) {
        if (worker.joinable()) {
            worker.join();
        }
    }
}

// Driver demonstrasi komputasi konkruen
int main() {
    try {
        ThreadPool pool(4);
        std::vector<std::future<uint64_t>> results;

        std::cout << "[Main] Enqueueing intensive cryptographic tasks...\n";

        for (int i = 0; i < 8; ++i) {
            results.emplace_back(pool.enqueue([i]() -> uint64_t {
                uint64_t accumulator = 0;
                for (uint64_t j = 0; j < 5'000'000; ++j) {
                    accumulator += (j ^ (i + 1));
                }
                return accumulator;
            }));
        }

        for (size_t i = 0; i < results.size(); ++i) {
            std::cout << "[Main] Task #" << i << " Result: " 
                      << results[i].get() << "\n";
        }
    } 
    catch (const std::exception& ex) {
        std::cerr << "[Fatal Exception]: " << ex.what() << "\n";
        return 1;
    }

    std::cout << "[Main] All tasks completed successfully. Pipeline closed.\n";
    return 0;
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Synchronous Blocking vs Multi-Threading vs Asynchronous Task (`std::async`) vs Lock-Free Data Structures

| Metrik / Dimensi | Blocking Sequential | Coarse-Grained Locking (`std::mutex`) | Task-Based (`std::async`) | Lock-Free Atomics (`CAS`) |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput (High Contention)** | Sangat Rendah | Sedang (Terhenti di serial lock) | Sedang hingga Tinggi | Ekstrem Tinggi |
| **Kompleksitas Kode** | Sangat Rendah | Rendah - Sedang | Sangat Rendah | Sangat Kompleks (ABA, Memory Reordering) |
| **Overhead CPU / Memori** | Minimum (Single stack) | Context-switching overhead, Stack per thread | Abstraksi Runtime OS overhead | CPU Polling / Retries overhead |
| **Risiko Deadlock** | Nol | **Sangat Tinggi** (ABBA lock inversion) | Rendah (Bisa starve) | **Nol Mutlak** |
| **Kemudahan Debugging** | Mudah / Linear | Moderat (Dukungan valgrind/TSAN) | Moderat | Sangat Sulit (Heisenbugs) |

### Memory Order Trade-offs
*   **`std::memory_order_seq_cst`:** *Safest choice*. Memaksa seluruh CPU core menyinkronkan bus instruction buffer. Memberikan perlindungan mutlak dari race condition urutan, namun mengorbankan pipeline throughput hingga 30-50% pada sistem dengan memory bus padat.
*   **`std::memory_order_relaxed`:** *Max performance*. Tidak melakukan serialisasi cache line. Hanya menjamin read/write pada variabel itu sendiri utuh. Sangat berbahaya jika digunakan untuk flag status dependensi data lain.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Spurious Wakeups (Pembangkitan Palsu)
Sebuah thread yang tertidur pada `std::condition_variable::wait()` dapat terbangun bahkan tanpa ada sinyal `notify_one()` atau `notify_all()`. Fenomena ini diakibatkan oleh mekanisme internal sinyal interupsi OS kernel (seperti delivery sinyal UNIX).
*Mitigasi:* Selalu bungkus pemanggilan wait dengan predikat status:
```cpp
// BENAR:
cv.wait(lock, [&]() { return is_ready; });

// SALAH (Sangat Rawan Bug):
if (!is_ready) {
    cv.wait(lock);
}
```

### 2. False Sharing
Dua variabel independen dialokasikan berdekatan di memori sehingga berada dalam satu baris cache line yang sama (biasanya 64 byte). Ketika Core 0 memodifikasi variabel A dan Core 1 memodifikasi variabel B secara bersamaan, CPU bus akan terus-menerus membatalkan (*invalidate*) cache line di kedua core, meskipun thread tidak berbagi variabel logis yang sama.
*Mitigasi:* Gunakan `alignas(std::hardware_destructive_interference_size)`.

### 3. Destruction Order & Dangling References
Meneruskan referensi variabel lokal stack ke thread yang berjalan di background (*detached* atau masa hidup thread lebih panjang daripada frame stack asal):
```cpp
void broken_spawn() {
    int local_data = 100;
    std::thread t([&local_data]() {
        // Stack local_data berpotensi hancur sebelum thread membaca nilai ini!
        std::cout << local_data << std::endl; // UNDEFINED BEHAVIOR
    });
    t.detach(); // Fatal
}
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. The "Lock Inversion" Deadlock (ABBA Problem)
**Kesalahan Fatal:** Thread 1 mengunci Mutex A lalu Mutex B. Di saat yang sama, Thread 2 mengunci Mutex B lalu Mutex A. Keduanya saling menunggu pelepasan kunci, memicu pembekuan sistem permanen.
```cpp
// SALAH:
void transfer(Account& from, Account& to, double amount) {
    std::unique_lock<std::mutex> lockA(from.mtx);
    std::unique_lock<std::mutex> lockB(to.mtx); // Deadlock jika operasi berlawanan terjadi
    from.balance -= amount;
    to.balance += amount;
}
```
**Solusi Modern C++ (C++17):** Gunakan `std::scoped_lock` yang mengadopsi algoritma penghindaran deadlock (*Deadlock-Avoidance Algorithm*, seperti *Resource Hierarchy Locking* atau *Chandy-Lamport*):
```cpp
// BENAR:
void transfer(Account& from, Account& to, double amount) {
    // Mengunci semua mutex secara simultan secara atomik tanpa memicu circular wait
    std::scoped_lock lock(from.mtx, to.mtx);
    from.balance -= amount;
    to.balance += amount;
}
```

### 2. Unhandled Exception Sebelum Join
Jika exception dilemparkan sebelum thread di-join, destruktor `std::thread` akan dieksekusi. Standar C++ mewajibkan jika sebuah `std::thread` dihancurkan dalam status *joinable*, `std::terminate()` **wajib dipanggil langsung**, mematikan seluruh proses.
```cpp
// SALAH:
void execute() {
    std::thread worker(do_work);
    throw std::runtime_error("Boom"); // Program langsung CRASH via std::terminate!
    worker.join();
}

// BENAR: Gunakan std::jthread (C++20) atau RAII Thread Guard wrapper
void execute() {
    std::jthread worker(do_work);
    throw std::runtime_error("Boom"); // Aman, destruktor std::jthread mengurus join()
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Prefer `std::jthread` over `std::thread` (C++20):** `std::jthread` menerapkan RAII penuh: secara implisit membatalkan via `stop_token` dan melakukan auto-join saat masa hidup objek berakhir.
2.  **Immutability By Default:** State yang tidak dapat dimutasi (*read-only*) sepenuhnya *thread-safe* tanpa memerlukan kunci sinkronisasi. Gunakan `const` secara agresif.
3.  **Minimize Lock Scope:** Kunci mutex sesingkat mungkin. Jangan pernah melakukan I/O disk, operasi jaringan, alokasi memori kompleks, atau memanggil fungsi eksternal yang tidak diketahui di dalam critical section.
4.  **Adopt Lock Hierarchies:** Jika program harus mengakuisisi lebih dari satu mutex dan tidak dapat menggunakan `std::scoped_lock`, terapkan sistem layering/peringkat ID pada mutex, dan selalu lakukan penguncian dari level numerik terendah ke tertinggi.
5.  **Thread Pool Isolation:** Pisahkan thread pool berdasarkan karakteristik beban kerja:
    *   *Compute-bound Pool:* Ukuran thread pool = Jumlah Core Fisik ($N$ Core).
    *   *I/O-bound Pool:* Ukuran thread pool = Relatif fleksibel terhadap profil latensi eksternal ($N \times 2$ hingga $N \times 10$).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Hardware-Aware Memory Alignment
Untuk menghindari dampak performa *False Sharing*, struktur data multi-core wajib dipisahkan pada batas cache-line menggunakan atribut alignment C++17:

```cpp
#include <new>

struct alignas(std::hardware_destructive_interference_size) ThreadLocalAccumulator {
    uint64_t partial_sum{0};
    uint8_t  padding_waste[56]; // Menghindari core tetangga menyentuh cache line yang sama
};
```

### 2. Lock-Contention Mitigation: Read-Copy-Update (RCU) & Shared Mutex
Jika sistem memiliki rasio 95% Read dan 5% Write, penggantian `std::mutex` tradisional dengan `std::shared_mutex` (C++17) memungkinkan ribuan thread membaca shared state secara bersamaan tanpa saling mengunci:

```cpp
#include <shared_mutex>

class ConfigRepository {
private:
    mutable std::shared_mutex rw_mtx_;
    std::string active_routing_url_;

public:
    std::string get_url() const {
        // Banyak pembaca dapat berjalan simultan
        std::shared_lock<std::shared_mutex> read_lock(rw_mtx_);
        return active_routing_url_;
    }

    void update_url(const std::string& new_url) {
        // Penulis mendapatkan hak eksklusif
        std::unique_lock<std::shared_mutex> write_lock(rw_mtx_);
        active_routing_url_ = new_url;
    }
};
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Thread Exhaustion (Denial-of-Service)
Membiarkan input pengguna memicu pembuatan OS thread secara bebas memungkinkan penyerang mengeksekusi serangan *Resource Exhaustion*. Kernel OS akan menolak alokasi thread baru (`pthread_create returns EAGAIN`), membuat proses mati mendadak.
*Hardening:* Selalu batasi kapasitas antrian tugas (*bounded queue*). Jika buffer antrian tugas penuh, kembalikan sinyal penolakan beban (*Backpressure/HTTP 429 Too Many Requests*) alih-alih terus mengalokasikan stack baru.

### 2. Time-of-Check to Time-of-Use (TOCTOU) In-Memory Race
Perhatikan bug race condition logika berikut:
```cpp
// VULNERABLE: Antara evaluasi isEmpty() dan pop(), state dapat diubah oleh thread lain!
if (!shared_queue.empty()) {
    // Context switch bisa terjadi di sini
    auto item = shared_queue.pop(); // Crash jika thread lain melakukan pop terlebih dahulu!
}
```
*Hardening:* Desain operasi API konkuren agar mengombinasikan query dan mutasi secara atomik:
```cpp
std::optional<T> try_pop(); // Mengembalikan nilai secara terproteksi jika tersedia
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Instrumentasi Thread Sanitizer (TSan)
Data race sering kali tidak terdeteksi selama pengujian fungsional unit test biasa karena bergantung pada *timing* CPU. Gunakan Clang/GCC ThreadSanitizer untuk melacak pelanggaran akses memori pada fase integrasi (CI/CD):

```bash
# Kompilasi dengan instrumentasi analisis data race
clang++ -std=c++20 -fsanitize=thread -g -O1 main.cpp -o hft_engine_tsan

# Jalankan biner. TSan akan mencetak stack trace lengkap jika terjadi Data Race
./hft_engine_tsan
```

### 2. Menamai Native Thread untuk Debugging Kernel
Thread sistem default tidak memiliki nama yang deskriptif saat dianalisis di debugger seperti GDB atau profiler `perf`:
```cpp
#include <pthread.h>

void name_current_thread(const char* name) {
#if defined(__linux__)
    pthread_setname_np(pthread_self(), name);
#endif
}
```
Saat terjadi *core dump*, analisis GDB akan langsung menampilkan nama worker:
```text
(gdb) info threads
  Id   Target Id                               Frame 
* 1    Thread 0x7ffff7a9c740 (HFT_Worker_01)   0x00007ffff7bc... in epoll_wait
  2    Thread 0x7ffff729b700 (HFT_Worker_02)   0x00007ffff7bc... in do_work
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```text
+-------------------+---------------------+---------------------------------------------------+
| Komponen C++      | Standar Diperkenalkan| Karakteristik / Panduan Utama                     |
+-------------------+---------------------+---------------------------------------------------+
| std::thread       | C++11               | Primitif dasar. Wajib explicit join()/detach().   |
| std::jthread      | C++20               | Auto-joining, mendukung cooperative cancellation.  |
| std::mutex        | C++11               | Mutual exclusion dasar. No copy, no move.         |
| std::scoped_lock  | C++17               | Mengunci N-mutex secara atomik (Anti-deadlock).   |
| std::shared_mutex | C++17               | Reader-Writer lock (Multiple Read, Single Write). |
| std::atomic<T>    | C++11               | Operasi atomik hardware-accelerated.              |
| memory_order      | C++11               | Menentukan constraint instruksi compiler & CPU.   |
| cv.wait(lck, pred)| C++11               | Mengeliminasi Spurious Wakeups.                  |
| alignas(64)       | C++11               | Mengeliminasi hardware cache-line False Sharing.  |
+-------------------+---------------------+---------------------------------------------------+
```

*   **Aturan 1:** Data Race terjadi jika $\ge 2$ thread mengakses lokasi memori identik secara bersamaan, minimal satu melakukan operasi write, dan tanpa sinkronisasi.
*   **Aturan 2:** `std::mutex` tidak boleh dikunci dua kali oleh thread yang sama (Gunakan `std::recursive_mutex` jika benar-benar terpaksa, namun ini biasanya indikasi kesalahan arsitektur).
*   **Aturan 3:** Jangan gunakan `volatile` untuk sinkronisasi thread di C++. Di C++, `volatile` dirancang khusus untuk memetakan memori perangkat keras I/O (MMIO), bukan untuk komunikasi *inter-thread safety*. Gunakan `std::atomic<T>`.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa yang terjadi secara spesifik menurut standar C++ jika sebuah objek `std::thread` dihancurkan dalam kondisi masih *joinable* (belum dipanggil `join()` maupun `detach()`)?**
   * A. Thread otomatis melakukan proses detach di background.
   * B. Thread dibatalkan seketika oleh sistem operasi.
   * C. Fungsi `std::terminate()` dipanggil langsung oleh runtime, mematikan seluruh program.
   * D. Memory leak terjadi di thread stack, tetapi program utama tetap berjalan.

2. **Manakah dari potongan kode berikut yang mengimplementasikan pemanggilan `std::condition_variable::wait` dengan benar terhadap proteksi *spurious wakeup*?**
   * A. `cv.wait(lock);`
   * B. `if (queue.empty()) cv.wait(lock);`
   * C. `cv.wait(lock, [&]() { return !queue.empty(); });`
   * D. `while (queue.empty()) { lock.unlock(); cv.wait(); }`

3. **Mengapa modifikasi `counter++` pada variabel bertipe data `int` biasa di dalam aplikasi multi-threaded menghasilkan kesalahan data race?**
   * A. Karena compiler C++ menolak kompilasi operasi aritmatika pada shared variable.
   * B. Karena `counter++` diuraikan menjadi tiga instruksi CPU terpisah: Read, Modify, Write yang dapat disela thread lain.
   * C. Karena nilai integer tidak dapat disimpan dalam register CPU multi-core.
   * D. Karena memori L1 cache tidak mendukung operasi penambahan nilai bilangan bulat.

4. **Karakteristik utama dari `std::jthread` yang diperkenalkan pada C++20 adalah:**
   * A. Memungkinkan eksekusi paralel pada level instruksi GPU.
   * B. Secara otomatis memanggil `detach()` saat thread kehabisan waktu pemrosesan.
   * C. Menghentikan thread seketika melalui sinyal `SIGKILL` saat objek keluar dari scope.
   * D. Mengadopsi prinsip RAII dengan memanggil `request_stop()` dan `join()` secara otomatis pada destruktornya.

5. **Apa fungsi utama dari `std::scoped_lock` yang diperkenalkan pada C++17 dibandingkan `std::lock_guard` tradisional?**
   * A. Mendukung penguncian mutex berulang kali (*recursive locking*).
   * B. Mampu mengunci beberapa objek mutex sekaligus secara atomik tanpa memicu risiko deadlock (ABBA).
   * C. Mengubah mutex menjadi antrian lock-free secara otomatis di tingkat hardware.
   * D. Mengurangi latensi sinkronisasi menjadi 0 nanodetik.

### Soal Tingkat Menengah (Intermediate)

6. **Diberikan skenario di mana dua thread memodifikasi dua field independen pada struct yang sama: `struct Data { int a; int b; };`. Field `a` dimodifikasi eksklusif oleh Core 0, dan `b` oleh Core 1. Meskipun secara logis bebas data race, sistem mengalami degradasi kinerja drastis. Fenomena arsitektural perangkat keras apa yang sedang terjadi?**
   * A. Pipeline Stall akibat Branch Misprediction.
   * B. False Sharing; kedua variabel berada pada cache line yang sama sehingga protokol koherensi cache (MESI) membatalkan baris cache terus-menerus.
   * C. TLB (Translation Lookaside Buffer) Thrashing.
   * D. Memory Bus Starvation akibat deadlock hardware.

7. **Pada C++ Memory Model, apa efek instruksional dari penggunaan `std::memory_order_release` pada sebuah operasi penulisan (*store*) atomic?**
   * A. Memaksa pembacaan data sebelum operasi ini dipindahkan ke setelah operasi tulis selesai.
   * B. Menjamin bahwa seluruh operasi pembacaan dan penulisan memori yang mendahului operasi release ini dalam program order tidak dapat diurutkan ulang (*reordered*) ke setelah operasi ini oleh kompilator maupun CPU.
   * C. Mengosongkan seluruh L3 cache CPU ke memori fisik DRAM.
   * D. Mengabaikan eksekusi thread lain hingga thread saat ini keluar dari fungsi.

8. **Mengapa kata kunci `volatile` dalam C++ tidak valid digunakan untuk membuat variabel penanda (*thread cancellation flag*) antar thread?**
   * A. Karena `volatile` hanya valid digunakan untuk tipe data floating point.
   * B. Karena `volatile` hanya menginstruksikan kompilator untuk tidak mengoptimasi pembacaan register; ia tidak menyisipkan memory barrier / fence instruksional perangkat keras dan tidak menjamin atomisitas.
   * C. Karena `volatile` memicu kompilator C++ untuk memblokir proses context switching pada kernel OS.
   * D. Karena `volatile` memaksa pemindahan variabel secara permanen ke hard disk (virtual swap memory).

9. **Apa konsekuensi dari memanggil fungsi `std::condition_variable::notify_one()` saat mutex pelindung predikat MASIH dalam status terkunci oleh thread pemanggil?**
   * A. Program akan mengalami exception `std::system_error`.
   * B. Terjadi deadlock instan pada pemanggil.
   * C. Notifikasi gagal dikirim dan hilang secara permanen.
   * D. *Pessimization Wakeup*: Thread yang tertidur dibangunkan oleh OS, mencoba mengakuisisi mutex, mendapati mutex masih terkunci oleh pemanggil, lalu terblokir kembali (overhead context-switch sia-sia).

10. **Bagaimana cara kerja algoritma *Work-Stealing* pada arsitektur thread pool tingkat lanjut?**
    * A. Thread master mencuri siklus CPU milik thread idle untuk mengeksekusi operasi kernel.
    * B. Setiap thread worker memiliki antrian kerja lokal sendiri; ketika antrian lokalnya kosong, ia mencuri tugas dari ujung antrian worker lain untuk mendistribusikan beban secara merata dan meminimalkan lock contention.
    * C. Thread mencuri alokasi RAM dari proses aplikasi lain ketika memori hampir habis.
    * D. Seluruh antrian tugas digabungkan ke dalam satu memori global non-blocking yang dieksekusi secara acak.

---

### Kunci Jawaban Kuis

1.  **C** — Berdasarkan klausul standar C++, destruktor `std::thread` yang joinable akan memanggil `std::terminate()`.
2.  **C** — Penggunaan overload lambda predikat menjamin pengecekan status saat thread bangun, memitigasi spurious wakeups.
3.  **B** — Operasi read-modify-write non-atomik pada tingkat instruksi mesin memicu data race (Undefined Behavior).
4.  **D** — `std::jthread` didesain untuk RAII thread management dan cooperative cancellation.
5.  **B** — `std::scoped_lock` menggunakan algoritma *deadlock avoidance* saat mengunci multiple mutex.
6.  **B** — False sharing terjadi ketika dua variabel independen berada pada cache line yang sama (biasanya 64 bytes) di CPU.
7.  **B** — Semantik release memastikan pembacaan/penulisan memori sebelumnya tersinkronisasi (*happens-before*) bagi thread lain yang membaca variabel tersebut via acquire.
8.  **B** — `volatile` di C++ hanya untuk memory-mapped I/O hardware, tidak menyediakan semantik *acquire-release* multi-core.
9.  **D** — Dikenal sebagai *pessimization wakeup*; disarankan membuka kunci (`lock.unlock()`) sesaat sebelum pemanggilan `notify_*`.
10. **B** — Work-stealing mempartisi antrian per thread untuk memaksimalkan afinitas cache dan meminimalkan perebutan kunci global.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang dan Bangun: Lock-Free Single-Producer Single-Consumer (SPSC) Ring Buffer

#### Sasaran Praktikum
Implementasikan antrian sirkular (*ring buffer*) berbasis template C++ yang sepenuhnya aman dari race condition antara **satu thread Producer** dan **satu thread Consumer** **TANPA** menggunakan `std::mutex`, `std::condition_variable`, atau primitif pemblokir kernel lainnya.

#### Spesifikasi Fungsional & Batasan Sistem
1.  **Struktur Data:** Menggunakan array linear flat berukuran tetap ($2^N$ elemen untuk optimasi bitwise modulo masking).
2.  **Primitif Sinkronisasi:** Hanya diperbolehkan menggunakan `std::atomic<size_t>` untuk menyimpan posisi `head_` (tulis) dan `tail_` (baca).
3.  **Memory Model Constraints:**
    *   Producer menulis data: Gunakan `std::memory_order_relaxed` saat membaca indeks sendiri, dan gunakan `std::memory_order_release` saat memperbarui indeks tulis agar data terlihat oleh Consumer.
    *   Consumer membaca data: Gunakan `std::memory_order_relaxed` saat membaca indeks sendiri, dan gunakan `std::memory_order_acquire` saat membaca indeks tulis Producer.
4.  **Hardware Optimization:** Variabel `head_` dan `tail_` **WAJIB** dipisahkan pada baris cache line yang berbeda menggunakan `alignas(hardware_destructive_interference_size)` untuk membuktikan eliminasi False Sharing.
5.  **API Interface Minimal:**
    ```cpp
    template<typename T, size_t Capacity>
    class SPSCRingBuffer {
    public:
        bool try_push(const T& item);
        bool try_pop(T& value);
    };
    ```

#### Metrik Pengujian
*   Bangun pengujian benchmark stres: 1 Producer thread memompa $100.000.000$ paket integer ke 1 Consumer thread.
*   Uji biner dengan ThreadSanitizer (`-fsanitize=thread`). Hasil pengujian **harus bersih 100% tanpa ada warning race condition**.
*   Bandingkan throughput (operasi per detik) antara SPSC Ring Buffer rancangan Anda terhadap antrian berbasis `std::mutex` tradisional. Anda diharapkan melihat peningkatan throughput antara 5x hingga 15x.