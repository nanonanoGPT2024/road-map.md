# BAB 08 — MODUL 01: SINKRONISASI KONKURENSI & MANAJEMEN THREADING MODERN

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Kurikulum:** CPP-02-LANG-B08M01
* **Kategori:** 02-Programming-Languages
* **Sub-kategori:** Advanced C++ Systems & Concurrency
* **Judul Topik:** Sinkronisasi Konkurensi & Manajemen Threading Modern (`std::jthread`, `std::mutex`, `std::scoped_lock`, dan Model Sinkronisasi Berbasis RAII)
* **Tingkat Kesulitan:** Advanced
* **Prasyarat:** Pemahaman mendalam tentang C++ Memory Model (Stack vs Heap), Pointers & Referensi, Mekanisme RAII (Resource Acquisition Is Initialization), Move Semantics, Exception Handling.
* **Target Kompiler:** Clang 16+ / GCC 13+ (Standar C++20 / C++23)

---

## SEKSI 02 — LEARNING OBJECTIVES

1. **Menganalisis (C4)** perbedaan mendasar antara eksekusi konkuren, paralel, dan *asynchronous* pada level arsitektur perangkat keras x86_64/ARM64 dan sistem operasi.
2. **Mengevaluasi (C5)** risiko konkurensi tingkat rendah, termasuk *data races*, *race conditions*, *deadlocks*, *livelocks*, dan *priority inversions*.
3. **Mengimplementasikan (C6)** manajemen thread deterministik yang aman terhadap eksepsi menggunakan primitif C++20 (`std::jthread`, `std::stop_token`).
4. **Membangun (C6)** struktur data *thread-safe* menggunakan strategi granularitas *locking* yang optimal (`std::mutex`, `std::shared_mutex`, `std::unique_lock`, `std::scoped_lock`).
5. **Mendiagnosis (C4)** bug konkurensi non-deterministik menggunakan ThreadSanitizer (TSan) dan analisis visualisasi *happens-before relationship*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma Sekuensial ke Konkuren

Dalam pemrograman sekuensial (single-threaded), state program dipandang sebagai deretan transisi diskrit yang berjalan lurus:

$$\text{State}_0 \xrightarrow{op_1} \text{State}_1 \xrightarrow{op_2} \text{State}_2$$

Model mental ini runtuh ketika memasuki pemrograman multi-threaded. Dalam lingkungan konkuren, sistem operasi bersama perangkat keras mengeksekusi beberapa aliran instruksi secara terinterleave (*interleaved*) atau bersamaan murni (*true parallel*) pada inti CPU yang berbeda.

```
Model Sekuensial:
Thread 1: [ A1 ] -> [ A2 ] -> [ A3 ] -> [ A4 ]

Model Konkuren (Interleaved / Parallel):
Thread 1: [ A1 ] --------> [ A2 ] ---------> [ A3 ] ---------> [ A4 ]
                \         /      \          /      \          /
Thread 2: -------> [ B1 ] --------> [ B2 ] ---------> [ B3 ] ------->
```

### Mental Model: The Vault and The Guard (RAII Locking)

Bayangkan memori bersama (*shared state*) sebagai sebuah lemari besi (The Vault). 
* Data di dalamnya tidak memiliki perlindungan bawaan.
* Kunci lemari besi adalah `std::mutex`. Mutex tidak menyembunyikan data secara fisik; ia hanya menyediakan token kepemilikan mutual exclusion.
* Pemrogram yang ceroboh mencoba mengakses isi lemari besi tanpa memeriksa kuncinya.
* Kunci RAII (`std::lock_guard`, `std::unique_lock`, `std::scoped_lock`) bertindak sebagai penjaga bersenjata: ia mengambil kunci sebelum pintu lemari terbuka, mengunci pintu kembali seketika penjaga keluar dari ruangan (keluar *scope*), bahkan jika bencana (eksepsi C++) terjadi di dalam ruangan tersebut.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Interaksi Eksekusi Thread, Mutex, dan Cache Coherency

```
+-------------------------------------------------------------------------+
|                              MAIN MEMORY                                |
|             Shared Variable: `counter` = 42                             |
+-------------------------------------------------------------------------+
                    ^                                   ^
                    | Read/Write                        | Read/Write
                    v                                   v
+---------------------------------------+ +---------------------------------------+
|              CPU CORE 0               | |              CPU CORE 1               |
|  +---------------------------------+  | |  +---------------------------------+  |
|  |           L1/L2 Cache           |  | |  |           L1/L2 Cache           |  |
|  |    Local Copy: `counter` = 42   |  | |  |    Local Copy: `counter` = 42   |  |
|  +---------------------------------+  | |  +---------------------------------+  |
|                   ^                   | |                   ^                   |
|                   | Bus Snooping/MESI | |                   | Bus Snooping/MESI |
|                   v                   | |                   v                   |
|  +---------------------------------+  | |  +---------------------------------+  |
|  | Execution Unit (Thread A)       |  | |  | Execution Unit (Thread B)       |  |
|  | Instruksi:                      |  | |  | Instruksi:                      |  |
|  | 1. Lock Mutex                   |  | |  | 1. Lock Mutex (BLOCKED)         |  |
|  | 2. Read counter                 |  | |  |    Menunggu Thread A Release    |  |
|  | 3. Modify counter               |  | |  | 2. Read counter                 |  |
|  | 4. Write back & Unlock Mutex    |  | |  | 3. Modify counter               |  |
+--+---------------------------------+-++-+--+---------------------------------+--+
                                       |
                   Kernel Futex Transition (System Call)
                                       v
                     +-----------------------------------+
                     | OS Scheduler Wait Queue (Thread B)|
                     +-----------------------------------+
```

### Siklus Hidup `std::jthread` (C++20 Cooperative Cancellation Lifecycle)

```
[Main Thread]                             [Worker jthread]
      |                                           |
      | 1. Instansiasi jthread(fn)                |
      +------------------------------------------>| (Status: Running)
      |                                           |
      |                                           | Loop: Cek stop_token
      |                                           | [ token.stop_requested() == false ]
      |                                           | Lakukan komputasi chunk...
      |                                           |
      | 2. request_stop() ATAU Destruktor jthread |
      |    (RAII Cleanup dimulai)                 |
      +--[Signal: stop_token diaktifkan]--------->|
      |                                           | [ token.stop_requested() == true ]
      | Menunggu via implicit join()...          | Menyelesaikan pembersihan lokal
      |                                           | Thread berhenti secara elegan
      |<------------------------------------------+ Terminate execution
      | 3. join() selesai                         
      v (Main Thread lanjut)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Bagaimana OS Memetakan Thread C++ (`std::thread` / `std::jthread`)

Di Linux (lingkungan POSIX), `std::thread` membungkus pustaka `pthread` melalui implementasi low-level runtime (misal `libstdc++` atau `libc++`).
* Panggilan `pthread_create()` mengeksekusi pemanggilan sistem `clone()` dengan flag spesifik: `CLONE_VM`, `CLONE_FS`, `CLONE_FILES`, `CLONE_SIGHAND`, `CLONE_THREAD`.
* Setiap thread C++ memiliki alokasi Stack memori independen (umumnya 2MB hingga 8MB default), namun berbagi *Virtual Address Space* yang sama (Heap, Data Segment, Code Segment) dengan thread lain dalam proses yang sama.

### 2. Mekanisme Internal Mutex: Fast Userspace Mutex (Futex)

Pada Linux x86_64, `std::mutex` tidak selalu memicu pemanggilan sistem (*system call*) kernel:
1. **Uncontended Case:** Thread mencoba mengunci mutex menggunakan instruksi atomik tingkat CPU seperti `CMPXCHG` (Compare-and-Swap). Jika tidak ada thread lain yang memegang lock, akuisisi selesai sepenuhnya di *userspace* (biaya sangat rendah, ~10-25 nanodetik).
2. **Contended Case:** Jika thread mendapati nilai atomik menunjukkan mutex sedang dikunci oleh core lain, runtime beralih ke syscall `sys_futex(FUTEX_WAIT)`. Kernel menangguhkan (*suspend*) thread yang memanggil, memasukkannya ke dalam antrean tunggu (*wait queue*), dan melakukan *context switch* ke thread lain.
3. **Release:** Saat thread pemilik selesai, ia mereset flag atomik. Jika ada thread lain yang mengantre, ia memanggil `sys_futex(FUTEX_WAKE)` untuk membangunkan satu atau lebih thread dari antrean kernel.

### 3. Keunggulan `std::jthread` dibanding `std::thread`

`std::thread` klasik C++11 memiliki kelemahan desain kritis: jika sebuah objek `std::thread` dihancurkan dalam keadaan *joinable* (belum dipanggil `.join()` atau `.detach()`), destruktornya akan memanggil `std::terminate()`, meruntuhkan seluruh proses aplikasi secara instan.

`std::jthread` (C++20) mengoreksi kelemahan ini dengan dua fitur utama:
* **Auto-Joining RAII:** Destruktor `std::jthread` secara otomatis memanggil `.request_stop()` diikuti oleh `.join()`.
* **Cooperative Cancellation:** Terintegrasi dengan `std::stop_token` dan `std::stop_source`, memungkinkan thread induk mengirim sinyal interupsi yang aman kepada thread pekerja (*worker thread*) tanpa pembatalan paksa yang berpotensi merusak state (*thread killing is unsafe*).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Data Race vs. Race Condition

Penting untuk membedakan dua istilah ini:

| Karakteristik | Data Race | Race Condition |
| :--- | :--- | :--- |
| **Definisi Standar C++** | Dua memory access terjadi secara simultan pada satu lokasi memori, minimal satu adalah *write*, dan tanpa sinkronisasi (*memory order/locks*). | Kesalahan logika semantik di mana kebenaran program bergantung pada waktu relatif atau urutan penjadwalan thread. |
| **Dampak Teknis** | **Undefined Behavior (UB)** murni. Kompiler bebas mengasumsikan UB tidak ada, menghasilkan kode biner korup atau optimasi register yang salah. | State data tidak valid, anomali logika bisnis, namun *bukan* UB pada level spesifikasi bahasa jika tidak melibatkan *data race*. |
| **Contoh** | Thread A mengeksekusi `x++` sementara Thread B membaca `x`, tanpa mutex atau atomik. | Thread memeriksa saldo rekening lalu menarik uang, namun thread lain menarik uang sebelum penarikan pertama dieksekusi (*Check-Then-Act flaw*). |

### Hubungan "Happens-Before" (C++ Memory Model)

Menurut spesifikasi ISO C++, urutan eksekusi antar thread diatur oleh relasi *happens-before*:
* Jika Operasi $A$ *happens-before* Operasi $B$, maka seluruh efek memori dari $A$ dijamin terlihat oleh thread yang mengeksekusi $B$.
* Sebuah mutex unlock pada Mutex $M$ secara formal *synchronizes-with* mutex lock berikutnya pada Mutex $M$ yang sama.
* Tanpa sinkronisasi eksplisit (*happens-before*), prosesor modern memiliki hak penuh untuk mereorder instruksi memori via *Out-of-Order Execution* (OoOE) dan *Store Buffers*, serta register caching.

### Kondisi Terjadinya Deadlock (The Coffman Conditions)

Deadlock hanya dapat terjadi jika **keempat** syarat berikut terpenuhi secara simultan:
1. **Mutual Exclusion:** Sumber daya dipegang secara eksklusif.
2. **Hold and Wait:** Thread memegang setidaknya satu sumber daya sambil menunggu akuisisi sumber daya lain.
3. **No Preemption:** Sumber daya tidak dapat diambil paksa dari thread yang sedang memegangnya.
4. **Circular Wait:** Terdapat rantai sirkular tertutup thread $\{T_1, T_2, \dots, T_n\}$ sedemikian rupa sehingga $T_1$ menunggu sumber daya yang dipegang $T_2$, dan $T_n$ menunggu sumber daya yang dipegang $T_1$.

*Eliminasi Coffman Condition #4 (Circular Wait) adalah tugas utama programmer C++ menggunakan strategi konsistensi urutan penguncian atau mekanisme `std::scoped_lock`.*

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode pengenalan C++20 yang mendemonstrasikan proteksi mutlak terhadap *data race*, pencegahan *deadlock* dengan banyak mutex, dan pembatalan kooperatif menggunakan `std::jthread`.

```cpp
#include <iostream>
#include <thread>
#include <mutex>
#include <vector>
#include <chrono>
#include <string>

// Struktur Akun Bank sederhana untuk demonstrasi transfer
struct BankAccount {
    int id;
    double balance;
    mutable std::mutex mtx; // 'mutable' agar dapat dikunci pada fungsi bertanda const

    BankAccount(int id_, double balance_) : id(id_), balance(balance_) {}
};

// Fungsi transfer aman menggunakan std::scoped_lock (Menghindari Deadlock secara matematis)
void transfer(BankAccount& from, BankAccount& to, double amount) {
    if (&from == &to) {
        return; // Mencegah self-deadlock
    }

    // std::scoped_lock (C++17) mengunci N mutex secara atomik menggunakan algoritma 
    // deadlock avoidance (seperti std::lock / resource ordering algorithm).
    std::scoped_lock lock(from.mtx, to.mtx);

    if (from.balance >= amount) {
        from.balance -= amount;
        to.balance += amount;
        std::cout << "[SUCCESS] Transfer $" << amount 
                  << " dari Akun " << from.id << " ke Akun " << to.id << "\n";
    } else {
        std::cout << "[REJECTED] Saldo tidak cukup pada Akun " << from.id << "\n";
    }
}

// Fungsi worker menggunakan cooperative cancellation std::jthread
void backgroundAuditor(std::stop_token stopToken, const BankAccount& acc1, const BankAccount& acc2) {
    std::cout << "[AUDITOR] Thread audit independen dimulai...\n";

    while (!stopToken.stop_requested()) {
        {
            // Mengunci kedua akun untuk membaca total konsistensi sistem
            std::scoped_lock lock(acc1.mtx, acc2.mtx);
            double total = acc1.balance + acc2.balance;
            std::cout << "[AUDITOR] Verifikasi Total Aset: $" << total << "\n";
        }

        // Tidur selama 50ms, namun dapat diinterupsi jika stopToken menerima request
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    std::cout << "[AUDITOR] Sinyal stop diterima. Melakukan pembersihan akhir dan keluar.\n";
}

int main() {
    BankAccount accountA(101, 1000.0);
    BankAccount accountB(102, 1000.0);

    // 1. Jalankan thread auditor independen (std::jthread otomatis join saat diderestruktur)
    std::jthread auditorThread(backgroundAuditor, std::cref(accountA), std::cref(accountB));

    // 2. Jalankan dua thread yang melakukan transfer silang secara agresif
    // Potensi Circular Wait deadlock jika tidak menggunakan std::scoped_lock:
    // Thread 1: Lock A lalu Lock B
    // Thread 2: Lock B lalu Lock A
    std::jthread worker1([&]() {
        for (int i = 0; i < 5; ++i) {
            transfer(accountA, accountB, 50.0);
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
    });

    std::jthread worker2([&]() {
        for (int i = 0; i < 5; ++i) {
            transfer(accountB, accountA, 25.0);
            std::this_thread::sleep_for(std::chrono::milliseconds(25));
        }
    });

    // Tunggu worker1 dan worker2 selesai
    worker1.join();
    worker2.join();

    std::cout << "[MAIN] Worker transfers selesai. Mengirim sinyal stop ke auditor...\n";
    
    // Explicit request stop (walau implisit dipanggil di destruktor auditorThread)
    auditorThread.request_stop();

    // auditorThread akan di-join() secara otomatis pada akhir scope main()
    return 0;
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis komponen esensial dari kode di Seksi 07:

1. **Baris 11 (`mutable std::mutex mtx;`):** 
   Kata kunci `mutable` mengizinkan penguncian mutex bahkan dalam fungsi anggota `const` (misalnya saat membaca representasi data objek). Mutex secara logis memodifikasi status internal hardware penguncian, bukan data bisnis objek.
2. **Baris 18 (`if (&from == &to)`):**
   Pemeriksaan alamat memori pointer. Jika entitas pengirim dan penerima identik, memanggil `std::scoped_lock` pada dua referensi mutex yang merujuk pada objek fisik yang sama akan memicu pemanggilan ganda pada mutex non-rekursif, menghasilkan status *Deadlock Seketika*.
3. **Baris 24 (`std::scoped_lock lock(from.mtx, to.mtx);`):**
   Fitur C++17 Class Template Argument Deduction (CTAD). Objek ini mengakuisisi seluruh mutex yang diberikan sebagai argumen tanpa menimbulkan deadlock, memanfaatkan algoritma pengurutan alamat internal untuk menghindari skenario Circular Wait. Objek ini merilis semua kunci secara otomatis saat keluar blok (`}`), bahkan jika terjadi eksepsi (Exception-Safe).
4. **Baris 35 (`void backgroundAuditor(std::stop_token stopToken, ...)`):**
   `std::jthread` secara otomatis meneruskan instance `std::stop_token` sebagai parameter pertama dari fungsi target jika fungsi tersebut menerimanya.
5. **Baris 38 (`while (!stopToken.stop_requested())`):**
   Pengecekan atomik status token kooperatif. Tidak menggunakan polling variabel global mentah yang rawan *race condition*.
6. **Baris 54 (`std::jthread auditorThread(...)`):**
   Instansiasi thread modern. Tidak seperti `std::thread`, `std::jthread` menjamin bahwa runtime tidak akan memanggil `std::terminate()` saat variabel `auditorThread` keluar dari *scope*.
7. **Baris 54 (`std::cref(accountA)`):**
   Thread konstruktor secara default menyalin (*copy-by-value*) argumen fungsinya. Untuk meneruskan argumen sebagai referensi konstan ke stack frame thread, pemrogram wajib membungkusnya dalam wrapper `std::reference_wrapper` via `std::cref()`.
8. **Baris 78 (`auditorThread.request_stop();`):**
   Mengubah status internal `std::stop_source` yang terhubung secara thread-safe, mengubah nilai `stopToken.stop_requested()` di thread pekerja menjadi `true`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Thread-Safe Ring Buffer / Bounded Queue untuk Ingestion Mesin Trading FinTech

Pada mesin perdagangan frekuensi tinggi (High-Frequency Trading Gateway) atau ingestion pipeline telemetri, ribuan order transaksi per detik diterima dari koneksi socket jaringan melalui beberapa *Network I/O Workers*. Data ini harus didistribusikan ke *Order Matching Engine Worker* melalui sebuah antrean berkapasitas terbatas (Bounded Queue) dengan latensi deterministik.

#### Tantangan Masalah:
1. **Producer-Consumer Race Condition:** Multi-producer menambahkan pesanan, Single-consumer memproses pesanan.
2. **Buffer Overflow & Memory Exhaustion:** Jika produser terlalu cepat dibanding konsumen, antrean tidak boleh bertumbuh tak hingga tanpa batas memory alokasi. Produser harus di-blokade (*backpressure*) saat antrean penuh.
3. **CPU Spurious Wakeups & Burnout:** Konsumen tidak boleh melakukan *busy-waiting* (loop CPU 100%). Konsumen harus tidur saat antrean kosong dan dibangunkan seketika data tersedia via `std::condition_variable`.
4. **Graceful Pipeline Teardown:** Ketika gateway menerima sinyal `SIGINT`/`SIGTERM`, semua sisa transaksi dalam antrean harus diproses hingga kosong sebelum aplikasi shutdown tanpa kebocoran memori atau dangling threads.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut implementasi lengkap Thread-Safe Bounded Blocking Queue dengan arsitektur C++20 modern:

```cpp
#include <iostream>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <optional>
#include <string>
#include <vector>
#include <chrono>
#include <thread>

// Representasi payload data transaksi trading
struct TradeOrder {
    uint64_t orderId;
    std::string symbol;
    double price;
    uint32_t quantity;
};

// Implementasi Thread-Safe Bounded Queue Production Grade
template <typename T>
class BoundedBlockingQueue {
private:
    std::queue<T> queue_;
    const size_t capacity_;
    mutable std::mutex mtx_;
    std::condition_variable cvNotEmpty_;
    std::condition_variable cvNotFull_;
    bool isShutdown_{false};

public:
    explicit BoundedBlockingQueue(size_t capacity) 
        : capacity_(capacity) {
        if (capacity == 0) {
            throw std::invalid_argument("Kapasitas antrean harus lebih besar dari 0.");
        }
    }

    ~BoundedBlockingQueue() {
        shutdown();
    }

    // Non-copyable, Non-movable untuk integritas sinkronisasi
    BoundedBlockingQueue(const BoundedBlockingQueue&) = delete;
    BoundedBlockingQueue& operator=(const BoundedBlockingQueue&) = delete;
    BoundedBlockingQueue(BoundedBlockingQueue&&) = delete;
    BoundedBlockingQueue& operator=(BoundedBlockingQueue&&) = delete;

    // Produser: Menambahkan item dengan blokade jika antrean penuh
    bool push(T item) {
        std::unique_lock<std::mutex> lock(mtx_);

        // Tunggu hingga antrean memiliki ruang ATAU queue dimatikan
        // cv.wait menerima Lock dan Predicate untuk mencegah spurious wakeups
        cvNotFull_.wait(lock, [this]() {
            return queue_.size() < capacity_ || isShutdown_;
        });

        if (isShutdown_) {
            return false; // Penolakan ingestion saat fase shutdown
        }

        queue_.push(std::move(item));

        // Beri tahu konsumen yang sedang tidur bahwa ada data baru
        lock.unlock(); // Unlock lebih awal sebelum notify untuk menghindari unneeded context switch
        cvNotEmpty_.notify_one();
        return true;
    }

    // Konsumen: Mengambil item dengan blokade jika antrean kosong
    std::optional<T> pop() {
        std::unique_lock<std::mutex> lock(mtx_);

        // Tunggu hingga antrean memiliki item ATAU queue dimatikan
        cvNotEmpty_.wait(lock, [this]() {
            return !queue_.empty() || isShutdown_;
        });

        // Drain mode: Jika shutdown namun queue masih memiliki data, habiskan datanya
        if (queue_.empty() && isShutdown_) {
            return std::nullopt;
        }

        T item = std::move(queue_.front());
        queue_.pop();

        // Beri tahu produser bahwa slot telah tersedia
        lock.unlock();
        cvNotFull_.notify_one();
        return item;
    }

    // Menghentikan antrean secara aman dan membangunkan seluruh thread yang tertahan
    void shutdown() {
        {
            std::lock_guard<std::mutex> lock(mtx_);
            if (isShutdown_) return;
            isShutdown_ = true;
        }
        // Bangunkan semua thread yang menunggu di cvNotFull dan cvNotEmpty
        cvNotEmpty_.notify_all();
        cvNotFull_.notify_all();
    }

    size_t size() const {
        std::lock_guard<std::mutex> lock(mtx_);
        return queue_.size();
    }
};

// Simulasi Pipeline Eksekusi
int main() {
    const size_t QUEUE_CAPACITY = 10;
    BoundedBlockingQueue<TradeOrder> orderQueue(QUEUE_CAPACITY);

    std::cout << "[SYSTEM] Memulai Trading Engine Pipeline...\n";

    // 1. Inisialisasi Consumer Thread (Matching Engine)
    std::jthread consumer([&orderQueue](std::stop_token st) {
        uint64_t processedCount = 0;
        while (!st.stop_requested()) {
            auto orderOpt = orderQueue.pop();
            if (!orderOpt.has_value()) {
                // Queue telah ditutup dan kosong sepenuhnya
                break;
            }

            const auto& order = *orderOpt;
            // Simulasi proses pencocokan order (matching)
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            processedCount++;
            
            if (processedCount % 5 == 0) {
                std::cout << "[ENGINE] Terproses: ID " << order.orderId 
                          << " | " << order.symbol 
                          << " | Qty: " << order.quantity 
                          << " @ $" << order.price << "\n";
            }
        }
        std::cout << "[ENGINE] Consumer selesai. Total order final: " << processedCount << "\n";
    });

    // 2. Inisialisasi Producer Threads (Network Gateways)
    std::vector<std::jthread> producers;
    producers.reserve(3);

    for (int pId = 0; pId < 3; ++pId) {
        producers.emplace_back([&orderQueue, pId]() {
            for (int i = 0; i < 15; ++i) {
                TradeOrder order{
                    .orderId = static_cast<uint64_t>(pId * 1000 + i),
                    .symbol = (pId % 2 == 0) ? "BTC/USD" : "ETH/USD",
                    .price = 50000.0 + (i * 10.5),
                    .quantity = static_cast<uint32_t>((i + 1) * 2)
                };

                if (!orderQueue.push(std::move(order))) {
                    std::cout << "[GATEWAY " << pId << "] Push gagal, antrean dimatikan.\n";
                    break;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            }
            std::cout << "[GATEWAY " << pId << "] Selesai mengirim data.\n";
        });
    }

    // Tunggu semua produser selesai mengirim data
    producers.clear(); // Memanggil destruktor jthread -> implicit join()
    std::cout << "[SYSTEM] Semua gateway selesai mengirim order. Menginisiasi shutdown antrean...\n";

    // Shutdown antrean: Izinkan antrean di-drain hingga kosong oleh consumer
    orderQueue.shutdown();

    // Consumer jthread akan selesai membaca sisa order dan exit naturally
    return 0;
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Matrix Perbandingan Mekanisme Sinkronisasi

| Primitif Sinkronisasi | Throughput Read | Throughput Write | Latensi / Overhead | Skenario Penggunaan Terbaik | Batasan Kritis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`std::mutex`** | Sedang | Sedang | Rendah (~25ns uncontended) | Mutasi state umum yang pendek dan cepat. | Memblokir semua thread (baik reader maupun writer). |
| **`std::shared_mutex`** | Sangat Tinggi | Rendah | Tinggi (~60-90ns karena tracking pembaca atomik) | Sistem *Read-Heavy* (misal: Routing Table, Konfigurasi Global Cache: >90% Read). | Berpotensi memicu *Writer Starvation* jika pembaca terus-menerus membanjiri antrean. |
| **Spinlock (`std::atomic_flag`)** | Tinggi (Core terisolasi) | Tinggi (Core terisolasi) | Sangat Rendah (<5ns jika lock instan) | Sistem Real-Time/Kernel di mana penundaan OS scheduler tidak ditoleransi; CS < 10 instruksi. | Mengonsumsi CPU 100%; bencana performa jika thread mengalami *preemption* saat memegang lock. |
| **Lock-Free Queue (`std::atomic`)** | Ekstrem | Ekstrem | Variatif (sensitif terhadap *CAS loop failures*) | Pipeline komunikasi data ultra-high-throughput antrian *Single-Producer Single-Consumer* (SPSC). | Kompleksitas implementasi tinggi; bahaya *ABA Problem*, memory ordering bugs jika salah implementasi. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Spurious Wakeups pada Condition Variable
* **Fenomena:** Thread yang tertahan pada `cv.wait()` dapat terbangun secara tiba-tiba tanpa ada pemanggilan `.notify_one()` atau `.notify_all()`. Ini terjadi pada implementasi kernel Linux/POSIX karena interupsi sinyal sistem (*OS context signals*).
* **Solusi Mutlak:** Selalu gunakan *Predicate Loop* atau bentuk overload `cv.wait(lock, Predicate)` seperti pada Baris 47 di Seksi 10. **Dilarang keras** memanggil `cv.wait(lock)` telanjang tanpa predikat boolean yang memeriksa status logis antrean.

### 2. Priority Inversion
* **Fenomena:** Thread prioritas rendah (L) memegang Mutex $M$. Thread prioritas tinggi (H) membutuhkan $M$ dan terblokir. Thread prioritas menengah (M), yang tidak membutuhkan $M$, mengambil alih CPU mendahului L karena prioritasnya lebih tinggi dari L. Akibatnya, H secara tidak langsung terhalang oleh M.
* **Solusi Sistemik:** Gunakan Mutex dengan protokol *Priority Inheritance* (disediakan pada pthread via `PTHREAD_PRIO_INHERIT` pada OS RTOS/Linux RT).

### 3. Lock Order Inversion Deadlock
* **Fenomena:** Thread 1 mengunci Mutex A lalu mencoba mengunci Mutex B. Pada saat yang sama, Thread 2 mengunci Mutex B lalu mencoba mengunci Mutex A.
* **Solusi Mutlak:** Gunakan `std::scoped_lock(mtx1, mtx2)` (C++17) yang secara otomatis menghitung *deadlock-free locking schedule*.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Memanggil Naked `.unlock()` Manual
```cpp
// SALAH: Rawan bocor jika terjadi exception di antara lock dan unlock
std::mutex m;
void unsafeProcess() {
    m.lock();
    doSomethingDangerous(); // Jika melempar std::runtime_error, mutex terkunci selamanya!
    m.unlock();
}

// BENAR: Menggunakan Idiom RAII (std::lock_guard atau std::unique_lock)
void safeProcess() {
    std::lock_guard<std::mutex> lock(m);
    doSomethingDangerous(); // Jika throw, destruktor lock otomatis melepas mutex!
}
```

### 2. Menggunakan `std::thread` Tanpa Perlindungan Destruktor
```cpp
// SALAH: Memanggil std::terminate() saat keluar scope jika join/detach terlupakan
void leakThread() {
    std::thread t([]() { compute(); });
    if (checkConditionFailed()) {
        return; // CRASH! std::terminate dipanggil karena t masih joinable!
    }
    t.join();
}

// BENAR: Gunakan std::jthread (C++20)
void safeThread() {
    std::jthread t([]() { compute(); });
    if (checkConditionFailed()) {
        return; // AMAN. Destruktor std::jthread otomatis memanggil join()
    }
}
```

### 3. Modifikasi Data Bersama Tanpa Perlindungan Mutex (Data Race)
```cpp
// SALAH: Data Race murni (Undefined Behavior)
int counter = 0;
void increment() { counter++; } // Rawan korupsi data

// BENAR: Gunakan atomic atau lindungi via mutex
std::atomic<int> counter{0};
void increment() { counter.fetch_add(1, std::memory_order_relaxed); }
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Jaga Critical Section Sesingkat Mungkin:** Hindari operasi I/O jaringan, pemanggilan disk (*file write*), alokasi memori berukuran besar, atau komputasi lambat di dalam blokade mutex.
2. **Deklarasikan Mutex Dekat dengan Data yang Dilindungi:** Kelompokkan mutex dan data dalam satu struct pembungkus untuk memperjelas kepemilikan.
3. **Patuhi Prinsip "Lock Order Hierarchy":** Jika arsitektur Anda mengharuskan penguncian hierarki bertingkat tanpa `std::scoped_lock`, tetapkan level hierarki global (misal: selalu kunci Mutex Database sebelum Mutex Cache).
4. **Berikan Nama pada Thread Anda:** Pustaka standar C++ belum memiliki API penamaan thread portabel. Gunakan ekstensi platform (`pthread_setname_np` di Linux) agar thread mudah diidentifikasi saat debugging post-mortem via *core dump*.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### False Sharing dan Cache Line Contention

Pada arsitektur modern (x86/ARM), data dibaca dari RAM ke dalam cache CPU dalam unit yang disebut **Cache Line** (biasanya 64 byte). 

Jika dua variabel independen yang diakses oleh dua thread berbeda berada pada satu cache line 64-byte yang sama, protokol cache coherency (MESI) akan terus-menerus membatalkan (*invalidate*) cache line di antara core CPU, menghasilkan penurunan performa drastis (*Cache Bouncing* / *Cache Ping-Pong*).

```cpp
#include <new>

// BURUK: Variabel berada dalam satu Cache Line (False Sharing)
struct BadCounters {
    uint64_t thread1_counter{0}; // Offset 0-7 byte
    uint64_t thread2_counter{0}; // Offset 8-15 byte (Satu cache line 64-byte!)
};

// OPTIMAL: Pisahkan variabel dengan Alignment spesifik Hardware
struct OptimalCounters {
    alignas(std::hardware_destructive_interference_size) uint64_t thread1_counter{0};
    alignas(std::hardware_destructive_interference_size) uint64_t thread2_counter{0};
};
```
*Catatan:* `std::hardware_destructive_interference_size` (disediakan di `<new>` sejak C++17) mengembalikan ukuran minimum byte yang diperlukan untuk menghindari false sharing secara arsitektural.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Time-of-Check to Time-of-Use (TOCTOU) pada Multithreading

Kerentanan keamanan konkurensi umum terjadi saat pemrogram memisahkan tahap verifikasi izin/keberadaan dengan tahap eksekusi.

```cpp
// VULNERABLE: Celah TOCTOU
if (authSession.isValid(sessionId)) { 
    // JENDELA WAKTU KERENTANAN (Time Window):
    // Thread lain dapat memanggil authSession.revoke(sessionId) di titik ini!
    executePrivilegedFinancialTransaction(sessionId); 
}

// HARDENED: Transaksi Atomic Mutex Scope
{
    std::lock_guard<std::mutex> lock(authSession.getMutex());
    if (authSession.isValidUnderLock(sessionId)) {
        executePrivilegedFinancialTransaction(sessionId);
    }
}
```

### Prinsip Thread-Sanitization Saat Deployment CI/CD
Selalu kompilasi test suite sistem Anda menggunakan **ThreadSanitizer (TSan)** pada pipeline CI/CD:
```bash
clang++ -std=c++20 -fsanitize=thread -g -O1 main.cpp -o app_tsan
./app_tsan
```
TSan menyisipkan instrumentasi memori untuk mendeteksi *data races* bahkan ketika *race* tersebut tidak menimbulkan crash secara kasat mata selama pengujian manual.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Debugging Deadlock dengan GDB (GNU Debugger)

Ketika program Anda mengalami *hang* total di lingkungan produksi akibat deadlock, ambil *core dump* atau sambungkan GDB ke proses yang berjalan:

```bash
# 1. Sambungkan GDB ke PID proses
gdb -p <PID>

# 2. Tampilkan semua thread yang aktif
(gdb) info threads

# 3. Tampilkan backtrace seluruh thread sekaligus
(gdb) thread apply all bt

# Output tipikal Deadlock akan menunjukkan beberapa thread terhenti di:
# __lll_lock_wait, futex_wait, atau std::__1::mutex::lock
```

### Logging Thread yang Aman
Menggunakan `std::cout` secara langsung dari beberapa thread menghasilkan output yang teracak (*garbled text*). Meskipun `std::cout` memiliki jaminan internal tidak crash (*no data race pada stream buffer*), karakter individual dari thread-thread berbeda akan bercampur baur.

Gunakan format sinkronisasi output berbasis buffer per-baris:
```cpp
#include <iostream>
#include <syncstream> // C++20

void safeLog(const std::string& message) {
    // std::osyncstream menjamin seluruh pesan di-flush secara atomik
    std::osyncstream(std::cout) << "[Thread " << std::this_thread::get_id() << "] " 
                                << message << '\n';
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Primitif Mutex & Locking

| Primitif / Kelas | Standar | Kapan Digunakan? | Fitur Utama |
| :--- | :--- | :--- | :--- |
| `std::mutex` | C++11 | Proteksi eksklusif dasar. | Sederhana, performa tinggi, non-reentrant. |
| `std::recursive_mutex` | C++11 | Hindari jika memungkinkan. Desain yang memerlukan ini biasanya merupakan *code smell*. | Mengizinkan penguncian ganda dari thread pemanggil yang sama. |
| `std::shared_mutex` | C++17 | Skenario *many readers, single writer*. | Mendukung `lock_shared()` dan `lock()`. |
| `std::lock_guard` | C++11 | Penguncian scope mendasar. | Ringan, RAII, non-movable, tidak bisa unlock manual. |
| `std::unique_lock` | C++11 | Diperlukan oleh `std::condition_variable`. | RAII, mendukung *deferred locking*, manual unlock/relock, *move-only*. |
| `std::scoped_lock` | C++17 | Mengunci $\ge 2$ mutex sekaligus. | Mencegah deadlock secara algoritmik (Deadlock-Free). |

### Manajemen Thread

| Fitur | `std::thread` (C++11) | `std::jthread` (C++20) |
| :--- | :--- | :--- |
| **Destruksi Tanpa Join** | Memanggil `std::terminate()` (Crash). | Otomatis meminta pembatalan & `.join()`. |
| **Cooperative Cancellation** | Tidak didukung secara native. | Mendukung `std::stop_token` & `std::stop_source`. |
| **Perpindahan Kepemilikan** | Move-Only. | Move-Only. |

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa yang terjadi secara spesifikasi jika sebuah objek `std::thread` keluar dari scope dalam keadaan *joinable* tanpa pernah dipanggil `.join()` atau `.detach()`?**
   * A) Thread otomatis berjalan di background sebagai daemon.
   * B) Kompiler melempar warning dan thread dihentikan paksa.
   * C) Runtime memanggil `std::terminate()`, meruntuhkan seluruh program.
   * D) Terjadi alokasi memori bocor (*memory leak*) namun program terus berjalan normal.

2. **Mengapa `std::lock_guard` lebih disukai dibandingkan memanggil manual `mtx.lock()` dan `mtx.unlock()`?**
   * A) Karena `std::lock_guard` lebih cepat 2x lipat daripada pemanggilan manual.
   * B) Karena `std::lock_guard` menjamin pelepasan kunci secara otomatis melalui prinsip RAII bahkan jika terjadi eksepsi.
   * C) Karena `std::lock_guard` bekerja secara lock-free di level hardware.
   * D) Karena `std::lock_guard` mengizinkan penguncian rekursif pada `std::mutex`.

3. **Manakah dari skenario berikut yang secara spesifik merupakan definisi formal dari sebuah *Data Race* dalam C++?**
   * A) Dua thread membaca lokasi memori yang sama secara simultan tanpa sinkronisasi.
   * B) Dua thread mencoba mengunci satu mutex yang sama pada waktu bersamaan.
   * C) Dua thread mengakses lokasi memori yang sama tanpa sinkronisasi, di mana minimal salah satu operasi adalah operasi penulisan (*write*).
   * D) Konsumen mencoba mengambil item dari antrean yang kosong.

4. **Apa fungsi utama dari kata kunci `mutable` pada variabel anggota `std::mutex` dalam sebuah kelas?**
   * A) Mengizinkan mutex tersebut diubah menjadi spinlock oleh kompiler.
   * B) Memungkinkan mutex diubah tipenya secara dinamis saat runtime.
   * C) Memungkinkan fungsi-fungsi anggota yang dideklarasikan `const` untuk mengunci dan melepas mutex tersebut.
   * D) Mencegah terjadinya *false sharing* pada memori cache.

5. **Apa fungsi dari `std::scoped_lock` yang diperkenalkan pada C++17 ketika menerima lebih dari satu mutex?**
   * A) Menjadikan seluruh mutex tersebut bersifat shared (read-only).
   * B) Mengunci mutex-mutex tersebut menggunakan algoritma pencegahan deadlock (Deadlock Avoidance).
   * C) Menjalankan setiap mutex pada core CPU yang berbeda.
   * D) Mempercepat waktu penguncian dengan mematikan pengecekan OS.

---

### Soal Tingkat Menengah (Intermediate)

6. **Mengapa pada penggunaan `std::condition_variable`, fungsi `wait()` hampir selalu membutuhkan instansiasi `std::unique_lock` dan bukan `std::lock_guard`?**
   * A) Karena `std::lock_guard` tidak dapat dialokasikan pada heap.
   * B) Karena antarmuka `cv.wait()` perlu melepas (*unlock*) mutex secara atomik saat tidur dan menguncinya kembali (*relock*) saat terbangun, kemampuan yang hanya dimiliki `std::unique_lock`.
   * C) Karena `std::unique_lock` menggunakan instruksi assembly yang berbeda dari `std::lock_guard`.
   * D) Karena `std::lock_guard` selalu memblokir thread lain secara permanen.

7. **Perhatikan cuplikan berikut:**
   ```cpp
   std::condition_variable cv;
   std::mutex mtx;
   bool ready = false;

   void waitWorker() {
       std::unique_lock<std::mutex> lock(mtx);
       while (!ready) {
           cv.wait(lock);
       }
       // Lakukan aksi...
   }
   ```
   **Mengapa klausa `while (!ready)` diperlukan alih-alih cukup menggunakan `if (!ready)`?**
   * A) Untuk menghindari kehabisan memori pada tumpukan stack.
   * B) Untuk melindungi program dari *Spurious Wakeup* (terbangunnya thread tanpa ada notifikasi valid).
   * C) Karena `cv.wait()` secara otomatis membalikkan nilai boolean variabel `ready`.
   * D) Karena standar C++ melarang percabangan `if` di dalam critical section.

8. **Apa dampak arsitektural dari fenomena *False Sharing* terhadap performa sistem multi-threaded?**
   * A) Menghasilkan crash *Segmentation Fault* akibat pelanggaran batas akses memori.
   * B) Menyebabkan prosesor membatalkan (*invalidate*) cache line secara konstan antar-core, mendegradasi drastis latensi throughput memori.
   * C) Memaksa sistem operasi mengubah mode eksekusi ke single-core.
   * D) Mengunci seluruh thread dalam status Deadlock secara instan.

9. **Fitur apa yang membedakan `std::jthread` (C++20) dari `std::thread` (C++11) terkait penghentian eksekusi thread secara elegan?**
   * A) `std::jthread` dapat membunuh (*kill/terminate*) thread paksa secara hardware.
   * B) `std::jthread` terintegrasi dengan cooperative cancellation framework via `std::stop_token`.
   * C) `std::jthread` mengalihkan thread ke proses terpisah (*forking*).
   * D) `std::jthread` tidak menggunakan alokasi stack sama sekali.

10. **Diberikan skenario: Thread A memegang Mutex 1 dan menunggu Mutex 2. Thread B memegang Mutex 2 dan menunggu Mutex 1. Kondisi Coffman mana yang berhasil dieliminasi jika kita mendesain kode sedemikian rupa sehingga Mutex 1 selalu dikunci sebelum Mutex 2 di seluruh thread?**
    * A) Mutual Exclusion.
    * B) Hold and Wait.
    * C) No Preemption.
    * D) Circular Wait.

---

### Kunci Jawaban & Pembahasan

1. **Jawaban: C**
   * *Pembahasan:* Menurut spesifikasi C++11 hingga C++23, destruktor `std::thread` yang dihancurkan saat statusnya masih *joinable* akan langsung mengeksekusi `std::terminate()`, meruntuhkan proses seketika tanpa stack unwinding normal.
2. **Jawaban: B**
   * *Pembahasan:* `std::lock_guard` mengimplementasikan pola RAII. Konstruktornya memanggil `.lock()` dan destruktornya memanggil `.unlock()`. Jika blok kode melempar eksepsi, stack unwinding akan mengeksekusi destruktor `lock_guard`, menjamin mutex tidak tergantung dalam status terkunci.
3. **Jawaban: C**
   * *Pembahasan:* Definisi formal ISO C++ Data Race adalah: minimal dua thread mengakses lokasi memori yang sama secara konkuren, setidaknya satu akses bersifat menulis (*write*), dan tidak ada sinkronisasi formal (*synchronizes-with*) di antara keduanya. Ini memicu Undefined Behavior.
4. **Jawaban: C**
   * *Pembahasan:* Mengunci mutex memerlukan modifikasi state internal mutex. Jika sebuah fungsi bertanda `const` (misal fungsi getter status), ia tidak dapat memanggil `.lock()` pada objek mutex biasa kecuali mutex tersebut ditandai dengan kata kunci `mutable`.
5. **Jawaban: B**
   * *Pembahasan:* `std::scoped_lock` menggunakan algoritma anti-deadlock (mirip dengan `std::lock`) untuk mengunci variadic mutex tanpa mempedulikan urutan passing parameter oleh pemanggil, secara efektif mengeliminasi skenario Circular Wait.
6. **Jawaban: B**
   * *Pembahasan:* `cv.wait()` perlu melepaskan lock secara atomik saat memasukkan thread ke dalam daftar tidur, dan secara atomik mengakuisisi lock kembali saat terbangun sebelum memeriksa kondisi. `std::lock_guard` tidak mengekspos metode `.unlock()` dan `.lock()` manual; hanya `std::unique_lock` yang memilikinya.
7. **Jawaban: B**
   * *Pembahasan:* Sistem operasi dapat membangunkan thread secara acak tanpa adanya sinyal eksplisit (*spurious wakeups*). Dengan menggunakan loop `while` (atau predikat lambda), thread yang terbangun secara palsu akan mengecek ulang predikat dan kembali tidur jika kondisi belum terpenuhi.
8. **Jawaban: B**
   * *Pembahasan:* *False Sharing* terjadi saat dua thread pada core berbeda memodifikasi variabel independen yang kebetulan berada pada satu Cache Line 64-byte yang sama. Protokol MESI memaksa cache line tersebut di-flush dan di-reload bolak-balik antar cache CPU L1/L2, memicu penurunan performa drastis tanpa error logika.
9. **Jawaban: B**
   * *Pembahasan:* `std::jthread` secara native menyediakan mekanisme cooperative cancellation melalui `std::stop_token`, memungkinkan thread luar mengirim permintaan berhenti yang dapat diperiksa secara berkala dan aman oleh thread pekerja.
10. **Jawaban: D**
    * *Pembahasan:* Memaksakan aturan pengurutan penguncian global yang strictly linear (*Lock Hierarchy Ordering*) mematahkan rantai sirkular, sehingga kondisi *Circular Wait* mustahil terbentuk secara matematis.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: Lock-Based Thread-Safe Priority Task Scheduler dengan Graceful Interruption

#### Deskripsi Spesifikasi:
Bangun sebuah sistem Task Scheduler konkuren berkinerja tinggi bernama `ThreadSafePriorityScheduler` dengan kriteria teknis berikut:

1. **Struktur Data Internal:**
   * Antrean tugas berbasis prioritas (`High`, `Medium`, `Low`).
   * Setiap tugas (`Task`) didefinisikan sebagai:
     ```cpp
     struct Task {
         int id;
         int priority; // Makin tinggi angka, makin tinggi prioritas
         std::function<void(std::stop_token)> work;
     };
     ```
2. **Kebutuhan Thread Pool:**
   * Alokasikan sekumpulan `std::jthread` sebagai *Worker Pool* (ukuran worker dikonfigurasi saat inisialisasi, misal sesuai `std::thread::hardware_concurrency()`).
   * Worker thread mengambil tugas dengan prioritas tertinggi yang tersedia.
   * Sinkronisasi mutlak menggunakan `std::mutex`, `std::unique_lock`, dan `std::condition_variable`.
3. **Mekanisme Stop & Graceful Draining:**
   * Sediakan method `submit(Task task)` untuk memasukkan pekerjaan baru.
   * Sediakan method `shutdown()` yang menghentikan penerimaan tugas baru, namun membiarkan semua tugas yang sudah berada di dalam antrean diselesaikan hingga tuntas oleh worker pool.
   * Sediakan method `emergencyStop()` yang langsung membatalkan seluruh tugas yang sedang berjalan melalui integrasi `std::stop_token` dari `std::jthread`, mengabaikan sisa tugas di antrean, dan segera melakukan terminate.
4. **Verifikasi Bebas Bug:**
   * Program wajib bersih dari kebocoran memori (Valgrind: *0 errors*).
   * Program wajib lolos kompilasi dan eksekusi di bawah **ThreadSanitizer** (`-fsanitize=thread`) tanpa memunculkan satu pun peringatan *Data Race*.