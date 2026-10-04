# SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** Back-End Systems & Systems Engineering (C++)
* **Kategori:** 02-Programming-Languages
* **Kode Modul:** CPP-0201
* **Nama Modul:** Memory Management & Resource Safety
* **Prasyarat Teknis:** CPP-0101 (Fundamental Syntax, Compilation Model, Translation Units), Pemahaman Dasar Model Memori Von Neumann (Stack, Heap, Register), Dasar Pointer & Referensi C++.
* **Standar Standarisasi ISO C++:** C++20 (ISO/IEC 14882:2020) dengan kompatibilitas backward C++17.
* **Tingkat Kesulitan:** Advanced Intermediate to Expert.

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara menyeluruh, peserta didik memiliki kapabilitas terukur untuk:

1. **Mengonstruksi Mental Model Virtual Memory:** Menganalisis transisi state alokasi pada Segment Memori (Text, Data, BSS, Stack, Heap) dan dampaknya terhadap cache line CPU serta sistem *paging* OS.
2. **Menguasai Filosofi RAII (Resource Acquisition Is Initialization):** Mengimplementasikan binding deterministik antara *lifetime* objek dan *scope* eksekusi untuk mengeliminasi *resource leakage* (file descriptors, sockets, mutex locks, heap memory).
3. **Menerapkan The Rule of Zero, Three, and Five Secara Presisi:** Menentukan arsitektur *copy/move constructors*, *copy/move assignment operators*, dan *destructors* sesuai paradigma *value semantics* dan *resource ownership*.
4. **Membedah Mekanisme Smart Pointer Internal:** Membedakan layout fisik, *overhead*, dan semantik kepemilikan antara `std::unique_ptr`, `std::shared_ptr`, dan `std::weak_ptr` (termasuk implikasi *control block* dan *custom deleters*).
5. **Mendeteksi dan Memitigasi Kerentanan Memori:** Mengidentifikasi dan mengeliminasi *Undefined Behavior* (UB) akibat *Dangling Pointer*, *Double Free*, *Use-After-Free* (UAF), dan *Memory Fragmentation* melalui instrumen statis dan dinamis (ASan, Valgrind, Clang-Tidy).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Filosofi Deterministik vs Non-Deterministik
C++ didesain di atas prinsip dasar: **"Zero Overhead Abstraction"** dan **"Deterministic Resource Destruction"**. Bahasa dengan runtime *Garbage Collection* (GC) seperti Java, Go, atau C# mendelegasikan siklus pembersihan memori ke proses background yang *non-deterministik*. Akibatnya, Anda tidak dapat menjamin kapan destruktor dijalankan, yang berbahaya jika sumber daya yang dikelola bersifat terbatas (seperti *file lock*, *kernel handle*, atau *GPU context*).

Di C++, **Scope adalah Pemilik Mutlak**. Ketika thread eksekusi keluar dari suatu scope (`}`), stack frame bergeser mundur, dan *destructor* untuk setiap *automatic variable* dipanggil seketika itu juga dalam urutan terbalik dari penciptaannya (LIFO).

```
Stack Unwinding (LIFO):
[Scope Entry] -> Buat Objek A -> Buat Objek B -> Buat Objek C
... Eksekusi Kode / Terjadi Exception ...
[Scope Exit]  <- Destruct C   <- Destruct B   <- Destruct A
```

### Resource Acquisition Is Initialization (RAII)
RAII bukan sekadar idiom memori, melainkan paradigma keselamatan sumber daya sistem:
* **Acquisition** terjadi di dalam *Constructor*. Jika konstruksi gagal (misal: memori habis, koneksi socket gagal), *exception* dilempar, dan objek dianggap tidak pernah ada; destruktor objek parsial tidak dipanggil, namun sub-objek yang sudah terkonstruksi akan dibersihkan secara otomatis.
* **Release** terjadi di dalam *Destructor*. Destruktor **wajib `noexcept`**. Melempar exception dari dalam destructor saat proses stack unwinding sedang berjalan akan langsung memicu `std::terminate()`.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Layout Memori Proses (Virtual Address Space x86_64)

```
+-------------------------------------------------------+ 0xFFFFFFFFFFFFFFFF
|                   Kernel Space                        |
|  (Memory-mapped hardware, interrupt handlers, dll.)   |
+-------------------------------------------------------+ 0x7FFFFFFFFFFFFFFF
|                        STACK                          |
|  [Stack Frame N] (Local vars, return addrs)           |
|         |                                             |
|         v (Tumbuh ke Bawah / Lower Addresses)         |
|                                                       |
|                        ...                            |
|                                                       |
|         ^ (Tumbuh ke Atas / Higher Addresses)         |
|         |                                             |
|                        HEAP                           |
|  (Alokasi dinamis via malloc, new, mmap)              |
+-------------------------------------------------------+
|          BSS Segment (Uninitialized Data)             |
|  (Static / Global variables bernilai 0 / default)     |
+-------------------------------------------------------+
|         Data Segment (Initialized Data)               |
|  (Static / Global variables dengan nilai eksplisit)   |
+-------------------------------------------------------+
|                   Text Segment (Code)                 |
|  (Instruksi mesin biner yang bersifat Read-Only)      |
+-------------------------------------------------------+ 0x0000000000000000
```

### 2. Topologi Internal Smart Pointer: `std::shared_ptr` dan `std::weak_ptr`

Ketika Anda memanggil `std::make_shared<T>()`, sistem mengalokasikan satu blok memori contiguous yang menampung objek target sekaligus *Control Block*.

```
std::shared_ptr<Resource> sptr1
std::weak_ptr<Resource>   wptr1
           |
           |             Memory Contiguous via std::make_shared
           |             +---------------------------------------------------------+
           +------------>| CONTROL BLOCK                                           |
                         |  - Strong Ref Count : 1 (dikelola oleh std::shared_ptr) |
                         |  - Weak Ref Count   : 1 (dikelola oleh std::weak_ptr)   |
                         |  - Custom Allocator : [Optional]                        |
                         |  - Custom Deleter   : [Optional]                        |
                         +---------------------------------------------------------+
                         | MANAGED OBJECT                                          |
                         |  - Resource payload: [Raw Data / Payload Bytes]         |
                         +---------------------------------------------------------+
```

* Siklus Hidup:
  1. Jika `Strong Ref Count == 0`: Managed Object **dihancurkan (destructor dipanggil)**.
  2. Memori *Control Block* tetap bertahan selama `Weak Ref Count > 0`.
  3. Jika `Strong Ref Count == 0` DAN `Weak Ref Count == 0`: Blok memori control block **dideallokasi secara fisik**.

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Stack vs Heap Allocator
* **Stack Allocator:** Eksekusi pemesanan memori di stack hanya membutuhkan satu instruksi CPU: memodifikasi *Stack Pointer* (`RSP` pada arsitektur x86_64, contoh: `sub rsp, 32`). Deallokasi setara dengan `add rsp, 32`. Tidak ada algoritma pencarian kompleks; latensi alokasi mendekati **0 nanodetik** (bersifat O(1)).
* **Heap Allocator (e.g., `glibc ptmalloc`, `jemalloc`, `tcmalloc`):**
  * Heap beroperasi di atas syscall sistem operasi: `brk()` / `sbrk()` untuk memindahkan batas program break, atau `mmap()` untuk memetakan halaman virtual memory anonim baru.
  * *Heap allocator* memelihara *free-lists* (misal: *small bins*, *large bins*, *tcache*). Operasi alokasi (`malloc`/`operator new`) mencari chunk memori yang cocok, melakukan metadata locking pada lingkungan multi-threading, memecah blok memori (*chunk splitting*), dan memperbarui *boundary tags*. Latensinya non-deterministik dan rentan terkena *cache misses*.

### 2. Mekanisme `operator new` vs Placement `new`
Keyword `new` di C++ mengeksekusi dua fase independen:
1. **Memory Allocation:** Memanggil `void* operator new(size_t)` untuk meminta raw memory.
2. **Object Construction:** Menjalankan konstruktor objek pada pointer memori mentah yang dihasilkan melalui instruksi runtime.

```cpp
// new ekspresi standar:
MyClass* ptr = new MyClass(arg);

// Ekuivalen internal yang dikerjakan compiler:
void* raw_mem = ::operator new(sizeof(MyClass)); // Tahap 1: Alokasi
MyClass* ptr = nullptr;
try {
    ptr = static_cast<MyClass*>(raw_mem);
    new (ptr) MyClass(arg);                      // Tahap 2: Placement new
} catch (...) {
    ::operator delete(raw_mem);                  // Rollback jika konstruksi melempar exception
    throw;
}
```

Placement new (`new (address) Type(...)`) **tidak mengalokasikan memori**, melainkan memanggil konstruktor secara eksplisit di alamat spesifik yang telah dipesan sebelumnya (misalnya di buffer stack atau custom arena).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Lifetime vs Scope
* **Scope:** Wilayah teks kode sumber di mana sebuah *identifier* dapat diakses secara valid (kompilator-sentris).
* **Lifetime:** Interval waktu runtime antara selesainya eksekusi konstruktor hingga dimulainya eksekusi destruktor dari suatu objek (runtime-sentris).

*Dangling references* muncul ketika sebuah objek telah mencapai akhir masa hidupnya (*end of lifetime*), tetapi referensi atau pointer ke alamat tersebut masih berada di dalam scope aktif.

### 2. The Rules of Zero, Three, and Five

Aturan ini menentukan bagaimana suatu class harus mengelola siklus hidup resource miliknya:

* **Rule of Zero:** Desain kelas Anda sedemikian rupa sehingga tidak memerlukan destruktor, copy constructor, move constructor, copy assignment, atau move assignment kustom. Gunakan tipe data modern yang telah mengimplementasikan RAII secara native (seperti `std::string`, `std::vector`, `std::unique_ptr`).

* **Rule of Three:** Jika sebuah class mengelola raw pointer / resource secara langsung dan membutuhkan **Destructor** eksplisit, kelas tersebut hampir dipastikan membutuhkan **Copy Constructor** dan **Copy Assignment Operator** kustom guna mencegah *shallow copy* yang memicu *double-free*.

* **Rule of Five:** Di era Modern C++ (C++11 ke atas), pengenalan *Move Semantics* mewajibkan penambahan **Move Constructor** dan **Move Assignment Operator** untuk efisiensi transfer kepemilikan resource temporer tanpa deep copying:
  1. `~Class()`
  2. `Class(const Class&)`
  3. `Class& operator=(const Class&)`
  4. `Class(Class&&) noexcept`
  5. `Class& operator=(Class&&) noexcept`

### 3. Pointer Aliasing & Strict Aliasing Rule
Kompilator mengasumsikan bahwa dua pointer dengan tipe dasar yang berbeda tidak menunjuk ke lokasi memori fisik yang sama (*Strict Aliasing Rule*). Melanggar aturan ini (misal: casting `float*` ke `int*` melalui raw C-style pointer cast) menyebabkan compiler menghasilkan optimasi instruksi reordering yang menghasilkan nilai register usang (*corrupted state* / Undefined Behavior). Standar Modern C++ mengatasi ini secara aman menggunakan `std::bit_cast` (sejak C++20) atau `std::memcpy`.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi komprehensif struktur data buffer memori dinamis yang mengimplementasikan **The Rule of Five**, penanganan resource RAII ketat, proteksi swap exception-safe, dan move-semantics terverifikasi.

```cpp
#include <iostream>
#include <utility>
#include <cstddef>
#include <algorithm>
#include <cstring>

class SafeRawBuffer {
private:
    std::size_t m_capacity;
    std::byte*  m_data;

public:
    // 1. Standard Constructor
    explicit SafeRawBuffer(std::size_t capacity)
        : m_capacity(capacity),
          m_data(capacity > 0 ? new std::byte[capacity]() : nullptr) {
        std::cout << "[LOG] Allocated: " << m_capacity << " bytes at " 
                  << static_cast<void*>(m_data) << '\n';
    }

    // Destructor
    ~SafeRawBuffer() noexcept {
        cleanup();
    }

    // 2. Copy Constructor (Deep Copy)
    SafeRawBuffer(const SafeRawBuffer& other)
        : m_capacity(other.m_capacity),
          m_data(other.m_capacity > 0 ? new std::byte[other.m_capacity] : nullptr) {
        if (m_data && other.m_data) {
            std::memcpy(m_data, other.m_data, m_capacity);
        }
        std::cout << "[LOG] Deep Copied: " << m_capacity << " bytes.\n";
    }

    // 3. Move Constructor (Resource Stealing)
    SafeRawBuffer(SafeRawBuffer&& other) noexcept
        : m_capacity(std::exchange(other.m_capacity, 0)),
          m_data(std::exchange(other.m_data, nullptr)) {
        std::cout << "[LOG] Moved (Constructor) Resource from " 
                  << static_cast<void*>(m_data) << '\n';
    }

    // 4. Copy Assignment Operator (Copy-and-Swap Idiom untuk Exception Safety)
    SafeRawBuffer& operator=(const SafeRawBuffer& other) {
        if (this != &other) {
            SafeRawBuffer temp(other); // Alokasi baru terjadi di temp
            swap(*this, temp);         // Tukar data internal; destructor temp menghapus data lama
        }
        std::cout << "[LOG] Copy Assigned via Swap.\n";
        return *this;
    }

    // 5. Move Assignment Operator
    SafeRawBuffer& operator=(SafeRawBuffer&& other) noexcept {
        if (this != &other) {
            cleanup(); // Bersihkan resource internal saat ini
            m_capacity = std::exchange(other.m_capacity, 0);
            m_data = std::exchange(other.m_data, nullptr);
            std::cout << "[LOG] Move Assigned Resource.\n";
        }
        return *this;
    }

    // Friend swap function untuk idiom copy-and-swap
    friend void swap(SafeRawBuffer& first, SafeRawBuffer& second) noexcept {
        using std::swap;
        swap(first.m_capacity, second.m_capacity);
        swap(first.m_data, second.m_data);
    }

    [[nodiscard]] std::size_t size() const noexcept { return m_capacity; }
    [[nodiscard]] std::byte* data() noexcept { return m_data; }
    [[nodiscard]] const std::byte* data() const noexcept { return m_data; }

private:
    void cleanup() noexcept {
        if (m_data) {
            std::cout << "[LOG] Deallocating: " << m_capacity << " bytes at " 
                      << static_cast<void*>(m_data) << '\n';
            delete[] m_data;
            m_data = nullptr;
            m_capacity = 0;
        }
    }
};

int main() {
    std::cout << "--- Inisialisasi Objek A ---\n";
    SafeRawBuffer bufA(1024);

    std::cout << "\n--- Operasi Copy Constructor (B dari A) ---\n";
    SafeRawBuffer bufB = bufA; 

    std::cout << "\n--- Operasi Move Constructor (C dari std::move(bufA)) ---\n";
    SafeRawBuffer bufC = std::move(bufA);

    std::cout << "\n--- Status Pointers Pasca-Move ---\n";
    std::cout << "bufA.data(): " << static_cast<void*>(bufA.data()) << " (Must be nullptr)\n";
    std::cout << "bufC.data(): " << static_cast<void*>(bufC.data()) << " (Must hold pointer)\n";

    std::cout << "\n--- Akhir Scope Main (Mulai Unwinding) ---\n";
    return 0;
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Konstruksi dan Eksekusi `SafeRawBuffer`
1. **Baris 13-17 (Konstruktor):** Menggunakan *member initializer list*. Inisialisasi `m_data` menggunakan ekspresi ternary ternary operator `capacity > 0 ? new std::byte[capacity]() : nullptr`. Penambahan tanda kurung `()` setelah array allocation memicu *value-initialization* (zero-initialization), mencegah pembacaan uninitialized memory.
2. **Baris 20-22 (Destruktor):** Ditandai `noexcept` mutlak. Mendelegasikan pembersihan ke private method `cleanup()`. Memastikan bahwa pointer yang dihapus di-set kembali ke `nullptr`. Memanggil `delete[] nullptr` aman secara spesifikasi standar ISO C++.
3. **Baris 25-33 (Copy Constructor):** Mengalokasikan blok memori independen baru (*deep copy*). Data byte disalin menggunakan `std::memcpy`. Jika alokasi `new std::byte[]` melempar `std::bad_alloc`, fungsi keluar sebelum memodifikasi status objek yang sedang dibentuk.
4. **Baris 36-41 (Move Constructor):** Menggunakan `std::exchange(other.m_data, nullptr)`. Utility ini mengambil nilai lama dari `other.m_data`, memasukkan nilai `nullptr` ke `other.m_data`, dan mengembalikan nilai lama tersebut untuk diisikan ke `m_data` objek target secara atomik dalam satu ekspresi. Hal ini mencegah objek asal (`other`) menjalankan destructor terhadap pointer yang valid.
5. **Baris 44-51 (Copy Assignment via Copy-and-Swap):** Membuat salinan lokal temporary `temp(other)`. Jika pembuatan `temp` gagal (karena out-of-memory), status internal objek target (`this`) belum mengalami perubahan sama sekali (memberikan garansi *Strong Exception Safety*). Operasi `swap` kemudian mengeksekusi perpindahan pointer tanpa kemungkinan throw exception.
6. **Baris 54-63 (Move Assignment):** Memeriksa *self-assignment guard* (`if (this != &other)`). Mengosongkan data yang sedang dipegang via `cleanup()`, kemudian menyedot pointer dari `other`.

---

# SEKSI 09 — STUDI KASUS NYATA

### Sistem Low-Latency Network Ingestion Engine
Pada arsitektur sistem backend *High-Frequency Trading* (HFT) atau *packet processing engine* (seperti router DPDK berbasis software), penggunaan `malloc`/`free` atau `new`/`delete` konvensional pada setiap frame paket network yang masuk (misal: 10 juta paket per detik) adalah anti-pattern fatal karena:
1. **Thread Contention:** Operasi lock-synchronization pada alokator global ketika beberapa thread worker meminta buffer secara simultan.
2. **Heap Fragmentation:** Paket berukuran bervariasi memecah contiguous memory space.
3. **Non-deterministic Latency Spikes:** Siklus alokasi kernel traversing menghasilkan latency tail (p99) yang tidak dapat diterima.

### Solusi Arsitektural: Fixed-Size Arena / Memory Pool Allocator
Kita membangun mekanisme RAII berbasis ring buffer atau fixed-block arena allocator. Alokasi terjadi **hanya satu kali** pada fase inisialisasi aplikasi (*pre-allocated flat buffer*). Saat runtime, thread worker mengambil potongan blok memori via *custom deleter* yang tidak membebaskan memori ke kernel, melainkan mengembalikannya kembali ke dalam lock-free pool.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut implementasi *Fixed-Size Memory Pool* berkinerja tinggi, thread-safe, dengan kontrol RAII otomatis menggunakan kustom deleter pada `std::unique_ptr`.

```cpp
#include <iostream>
#include <vector>
#include <memory>
#include <mutex>
#include <cstddef>
#include <cstdint>

class PacketMemoryPool {
public:
    static constexpr std::size_t BLOCK_SIZE = 2048; // 2KB per packet block

    explicit PacketMemoryPool(std::size_t block_count)
        : m_pool_storage(block_count * BLOCK_SIZE),
          m_block_count(block_count) {
        m_free_list.reserve(block_count);
        for (std::size_t i = 0; i < block_count; ++i) {
            m_free_list.push_back(&m_pool_storage[i * BLOCK_SIZE]);
        }
    }

    ~PacketMemoryPool() = default;
    
    // Disable Copying to enforce strict resource identity
    PacketMemoryPool(const PacketMemoryPool&) = delete;
    PacketMemoryPool& operator=(const PacketMemoryPool&) = delete;

    // Custom Deleter Functor
    struct PoolDeleter {
        PacketMemoryPool* pool;

        void operator()(std::byte* ptr) const noexcept {
            if (pool && ptr) {
                pool->return_block(ptr);
            }
        }
    };

    using PacketHandle = std::unique_ptr<std::byte[], PoolDeleter>;

    // Acquire block from pool wrapped in an Exception-Safe RAII Handle
    [[nodiscard]] PacketHandle acquire_packet() {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (m_free_list.empty()) {
            throw std::bad_alloc(); // Pool exhausted
        }

        std::byte* block = m_free_list.back();
        m_free_list.pop_back();

        return PacketHandle(block, PoolDeleter{this});
    }

    [[nodiscard]] std::size_t available_blocks() const noexcept {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_free_list.size();
    }

private:
    void return_block(std::byte* ptr) noexcept {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_free_list.push_back(ptr);
        // Destructor unik tidak memanggil delete[], melainkan mengembalikan pointer ke pool list
    }

    std::vector<std::byte> m_pool_storage;
    std::vector<std::byte*> m_free_list;
    std::size_t m_block_count;
    mutable std::mutex m_mutex;
};

// Simulasi Konsumsi Network Pipeline
void process_network_frame(PacketMemoryPool& pool, int frame_id) {
    try {
        // Ambil buffer. Jika scope berakhir, Custom Deleter otomatis mengembalikan blok ke pool.
        auto packet = pool.acquire_packet();
        
        // Manipulasi payload buffer
        packet[0] = static_cast<std::byte>(0xAA);
        packet[1] = static_cast<std::byte>(frame_id & 0xFF);

        std::cout << "[Worker] Processed frame " << frame_id 
                  << " at block address: " << static_cast<void*>(packet.get()) 
                  << " | Remaining pool blocks: " << pool.available_blocks() << '\n';

    } catch (const std::bad_alloc&) {
        std::cerr << "[CRITICAL] Packet drop: Pool exhaustion on frame " << frame_id << '\n';
    }
}

int main() {
    constexpr std::size_t TOTAL_BLOCKS = 2;
    PacketMemoryPool network_pool(TOTAL_BLOCKS);

    std::cout << "Initial available blocks: " << network_pool.available_blocks() << "\n\n";

    {
        std::cout << "--- Mengambil 2 Handle Sekaligus ---\n";
        auto packet1 = network_pool.acquire_packet();
        std::cout << "Allocated packet 1. Sisa: " << network_pool.available_blocks() << '\n';

        {
            auto packet2 = network_pool.acquire_packet();
            std::cout << "Allocated packet 2. Sisa: " << network_pool.available_blocks() << '\n';

            // Memaksa eksekusi alokasi ketiga (harus gagal)
            process_network_frame(network_pool, 999);
            std::cout << "Keluar scope internal...\n";
        } // packet2 dihancurkan di sini: Deleter otomatis mengembalikan block ke pool!

        std::cout << "Pasca keluarnya packet2. Sisa: " << network_pool.available_blocks() << '\n';
    } // packet1 dihancurkan di sini.

    std::cout << "Semua resource keluar scope. Sisa pool: " << network_pool.available_blocks() << '\n';

    return 0;
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Matrix Karakteristik Model Kepemilikan Memori

| Parameter | Raw Pointer (`T*`) | `std::unique_ptr<T>` | `std::shared_ptr<T>` | Arena/Pool Allocator |
| :--- | :--- | :--- | :--- | :--- |
| **Ownership Semantics** | Tidak ada (Observasi saja) | Eksklusif / Tunggal (*Move-only*) | Bersama (*Shared/Reference Counted*) | Manajerial Terpusat |
| **Memory Overhead** | 0 bytes (hanya ukuran pointer 64-bit) | 0 bytes (Zero-overhead jika stateful deleter dihindari) | 16–24 bytes (Pointer payload + pointer Control Block) | Minimal overhead metadata pada free-list |
| **Time Overhead (Allocation)** | Tergantung allocator (`malloc`) | Setara alokasi raw heap | 1x Alokasi gabungan jika memakai `make_shared` | $O(1)$ deterministik register pop |
| **Time Overhead (Dereference)**| $O(1)$ Direct dereference | $O(1)$ Setara raw pointer | $O(1)$ Setara raw pointer | $O(1)$ Setara raw pointer |
| **Time Overhead (Destruction)** | Manual non-deterministik | $O(1)$ Langsung memanggil destructor | Atomic decrement: Membutuhkan `lock inc/dec` bus cycle | Sangat cepat (dibersihkan massal atau push to list) |
| **Thread Safety Overhead** | Tidak ada proteksi | Tidak ada proteksi | Atomic Ref Count sync (overhead CPU bus lock) | Mutex / Lock-free atomic list |
| **Cache Locality** | Buruk jika terfragmentasi | Sesuai layout memori heap | Terbagi antara Payload & Control Block | Sangat tinggi (Contiguous Virtual Memory) |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Circular Reference pada `std::shared_ptr`
Jika dua objek saling mereferensikan satu sama lain via `std::shared_ptr`, *reference count* internal masing-masing tidak akan pernah mencapai 0. Keduanya tidak akan pernah dihancurkan, mengakibatkan *permanent memory leak*.

```
   +-----------+                    +-----------+
   |  Node A   | --- shared_ptr --> |  Node B   |
   |           | <-- shared_ptr --- |           |
   +-----------+                    +-----------+
   Ref Count: 1                     Ref Count: 1
```
*Solusi:* Patahkan siklus siklis dengan mengubah salah satu relasi menjadi `std::weak_ptr`.

### 2. Double-Ownership Melalui Pemanggilan Constructor Ulang dari Raw Pointer
Membuat dua objek `shared_ptr` independen dari pointer mentah yang sama adalah bencana:

```cpp
T* raw = new T();
std::shared_ptr<T> sp1(raw);
std::shared_ptr<T> sp2(raw); // FATAL BUG: sp1 dan sp2 membuat dua control block independen!
// Ketika sp1 dan sp2 keluar scope, objek *raw akan mengalami DOUBLE-FREE.
```
*Solusi:* Hindari pemaparan pointer mentah. Gunakan `std::make_shared` secara eksklusif. Jika referensi balik (`this`) dibutuhkan di dalam member function, inherit dari `std::enable_shared_from_this<T>` dan gunakan `shared_from_this()`.

### 3. Eksepsi pada Constructor Arguments (Pre-C++17 Pitfall)
Sebelum C++17 memperkenalkan evaluasi urutan argumen yang diperketat, kode seperti ini:
```cpp
// Berbahaya jika fungsi eksekusi argumen dievaluasi secara interlaced:
process(std::unique_ptr<T>(new T()), function_that_might_throw());
```
Jika `new T()` berhasil dialokasikan, lalu `function_that_might_throw()` melempar exception sebelum konstruktor `unique_ptr` sempat mengikat pointer mentah tersebut, memori `T` bocor permanen. Gunakan selalu `std::make_unique` (C++14).

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Returning Dangling References dari Local Scope

```cpp
// SALAH (Undefined Behavior)
const std::string& get_temporary_path() {
    std::string path = "/tmp/app.sock";
    return path; // CRITICAL: Referensi ke local stack object yang dihancurkan saat '}'
}

// BENAR (Modern C++ RVO - Return Value Optimization)
std::string get_temporary_path() {
    std::string path = "/tmp/app.sock";
    return path; // Mengembalikan by-value; compiler memicu zero-cost NRVO/Move.
}
```

### 2. Menggunakan `std::shared_ptr` Ketika `std::unique_ptr` Mencukupi
*Anti-pattern:* Menggunakan `std::shared_ptr` sebagai tipe default "karena mudah dan aman".
*Dampak Buruk:* `std::shared_ptr` membutuhkan kontrol alokasi metadata dinamis dan operasi inter-thread memory barrier atomic pada reference counter, menurunkan performa cache dan konkurensi.
*Aturan:* Mulai selalu dengan `std::unique_ptr`. Promosikan ke `std::shared_ptr` hanya jika desain arsitektur menuntut *shared ownership* non-hirarkis sejati.

### 3. Lambda Capture by Reference pada Asynchronous/Detached Context

```cpp
void enqueue_work() {
    int local_data = 42;
    thread_pool.submit([&local_data]() { 
        // FATAL: local_data mungkin sudah hancur jika enqueue_work() return
        // sebelum task ini dieksekusi di background thread!
        std::cout << local_data << '\n'; 
    });
}

// PERBAIKAN:
void enqueue_work() {
    int local_data = 42;
    thread_pool.submit([local_data]() { // Capture by value atau via move-init capture
        std::cout << local_data << '\n';
    });
}
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

### C++ Core Guidelines Compliance
1. **R.11: Avoid calling `new` and `delete` explicitly.** Gunakan container standar (`std::vector`, `std::string`) atau smart pointer factory function (`std::make_unique`, `std::make_shared`).
2. **R.21: Prefer `unique_ptr` over `shared_ptr` unless you need to share ownership.**
3. **F.16: For "in" parameters, pass cheap-to-copy types by value and others by reference to const.** Jangan mengoper `std::unique_ptr` atau `std::shared_ptr` sebagai parameter jika fungsi tersebut hanya meminjam (*read-only*) objek yang dikandungnya; operkan `const T&` atau `T*`.
4. **C.35: A base class destructor should be either public and virtual, or protected and non-virtual.** Menghindari pemanggilan destruktor turunan yang terabaikan saat menghapus via pointer basis:

```cpp
class Interface {
public:
    virtual ~Interface() = default; // Menjamin virtual dispatch pada hierarki polymorphism
    virtual void execute() = 0;
};
```

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Small Buffer Optimization (SBO)
Library modern (seperti implementasi `std::string`, `std::function`, atau `boost::container::small_vector`) menerapkan teknik SBO.

```
Layout std::string (umumnya 24 atau 32 bytes):
+-------------------------------+-----------------------+
|  Pointer ke Heap (jika besar) | Kapasitas & Ukuran    |  (Mode Dynamic)
+-------------------------------+-----------------------+
|  Internal Array buffer[15]    | Ukuran lokal          |  (Mode SBO: 0 alokasi heap!)
+-------------------------------+-----------------------+
```

Jika payload data lebih kecil dari ukuran internal union buffer (umumnya 15-22 bytes), tidak ada syscall `malloc` yang diluncurkan. String dialokasikan secara instan di dalam stack frame objek itu sendiri.

### Alignment dan Cache-Line Bounding
CPUs membaca memori melalui *Cache Lines* (umumnya 64 bytes pada arsitektur modern x86/ARM). Objek yang melewati batas cache-line (*unaligned access*) memaksa CPU mengambil 2 cache line untuk membaca satu data tunggal, mengurangi efisiensi bus memori hingga 50%.

```cpp
struct alignas(64) HighThroughputAlignedData {
    uint64_t metric_counter;
    uint64_t last_timestamp;
    // Data ini dipaksa berjarak 64-byte untuk menghindari False Sharing pada Multi-core processing
};
```

---

# SEKSI 16 — KEAMANAN & HARDENING

Memori C++ yang tidak aman menjadi vektor exploitasi utama: CVE (*Common Vulnerabilities and Exposures*) seperti *Heap Buffer Overflow*, *Use-After-Free*, dan *Return-Oriented Programming (ROP)* berasal dari kelemahan manajemen memori mentah.

### 1. Instrumentasi Compiler Sanitizers
Wajibkan integrasi *AddressSanitizer* (ASan) dan *UndefinedBehaviorSanitizer* (UBSan) pada environment CI/CD dan profil testing.

Flags GCC / Clang:
```bash
g++ -std=c++20 -fsanitize=address,undefined -fno-omit-frame-pointer -g -O1 main.cpp -o app_sanitized
```
* **AddressSanitizer:** Menyuntikkan instruksi pengecekan (*Shadow Memory*) di setiap akses memory address load/store. Mendeteksi out-of-bounds stack/heap access dan use-after-free dalam hitungan instruksi saat eksekusi.
* **UndefinedBehaviorSanitizer:** Mendeteksi integer overflow, alignment violations, null-pointer dereferencing.

### 2. Zeroization of Sensitive Data
Destruktor standar tidak membersihkan nilai memory register saat membebaskan memori. Sisa kredensial otentikasi (kata sandi, privat key RSA) dapat dibaca attacker melalui *Cold Boot Attacks* atau *Heartbleed-like vulnerabilities*.

Gunakan secure zeroization intrinsics OS (bukan `memset`, yang dapat dieliminasi oleh compiler dead-code elimination optimization):
```cpp
#include <cstring>

void secure_clear_memory(void* v, size_t n) {
#if defined(__STDC_LIB_EXT1__)
    memset_s(v, n, 0, n);
#elif defined(_WIN32)
    SecureZeroMemory(v, n);
#else
    // Memaksa akses volatile agar optimizer tidak menghapus pemanggilan fungsi
    volatile unsigned char* p = static_cast<volatile unsigned char*>(v);
    while (n--) *p++ = 0;
#endif
}
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Global Operator Tracking untuk Menemukan Alokasi Tersembunyi
Overriding global `operator new` dan `delete` adalah teknik instrumentasi ampuh untuk memantau metrics alokasi secara live tanpa mengganggu integritas codebase produksi.

```cpp
#include <iostream>
#include <cstdlib>
#include <atomic>

static std::atomic<std::size_t> g_allocated_bytes{0};
static std::atomic<std::size_t> g_active_allocations{0};

void* operator new(std::size_t size) {
    g_allocated_bytes += size;
    ++g_active_allocations;
    
    // Menambahkan header metadata tersembunyi untuk melacak ukuran blok saat deallokasi
    void* ptr = std::malloc(size);
    if (!ptr) throw std::bad_alloc();
    return ptr;
}

void operator delete(void* ptr) noexcept {
    if (!ptr) return;
    --g_active_allocations;
    std::free(ptr);
}

void print_memory_metrics() {
    std::cout << "[METRICS] Current Active Allocs: " << g_active_allocations.load() 
              << " | Total Allocated: " << g_allocated_bytes.load() << " bytes\n";
}
```

### Debugging Menggunakan Valgrind Memcheck
Eksekusi binary binary native tanpa modifikasi untuk melacak memory leak residual:
```bash
valgrind --leak-check=full --show-leak-kinds=all --track-origins=yes ./app_binary
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

1. **RAII is King:** Ikatkan masa hidup memori, database connection, mutex, file pointer pada masa hidup objek lokal stack.
2. **Rule of Zero:** Prioritaskan arsitektur tanpa kustom copy/move/destructor. Delegasikan ke tipe library standar (`std::string`, `std::unique_ptr`).
3. **The Rule of Five:** Jika Anda menulis salah satu dari Destructor/Copy/Move, tulis kelimanya secara eksplisit.
4. **Smart Pointer Triad:**
   * `std::unique_ptr<T>`: Kepemilikan eksklusif. Tanpa runtime overhead. *Move-only*.
   * `std::shared_ptr<T>`: Kepemilikan bersama (*reference count* atomik). Hindari kecuali sangat dibutuhkan. Gunakan `std::make_shared` untuk menyatukan alokasi.
   * `std::weak_ptr<T>`: Referensi observer non-owning ke `shared_ptr`. Mencegah circular leaks. Gunakan `.lock()` sebelum mengakses.
5. **Noexcept Destructors:** Destruktor tidak boleh melempar exception (`noexcept` by default). Destruktor yang melempar exception saat stack unwinding akan langsung mengeksekusi crash fatal `std::terminate()`.
6. **Eliminasi Raw Calls:** Hindari `new`, `new[]`, `delete`, `delete[]` mentah dalam kode aplikasi modern tingkat tinggi.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)
1. **Pertanyaan:** Apa perbedaan fundamental alokasi variabel di dalam Stack frame dibandingkan alokasi melalui `malloc`/`operator new` di Heap?
   * *Jawaban:* Stack allocation hanya memindahkan register pointer CPU (instruksi O(1) deterministik instan) dan memori dibersihkan otomatis saat keluar scope secara LIFO. Heap allocation mencari blok memori bebas melalui kernel runtime allocator, membutuhkan proteksi concurrent lock, memakan latensi non-deterministik, dan wajib dibersihkan secara manual/RAII.
2. **Pertanyaan:** Mengapa pemanggilan `delete` pada raw pointer tipe turunan melalui basis pointer yang tidak memiliki `virtual ~Destructor()` menghasilkan Undefined Behavior?
   * *Jawaban:* Tanpa destruktor virtual, kompilator menyelesaikan pemanggilan destruktor via *static binding* (berdasarkan tipe pointer basis, bukan tipe objek runtime yang sebenarnya). Akibatnya, destruktor kelas turunan beserta resource yang dikelolanya tidak pernah dipanggil, dan blok memory alignment yang dideallokasi bisa salah ukuran.
3. **Pertanyaan:** Mengapa kita tidak boleh memanggil `std::make_shared` jika ukuran objek sangat besar dan terdapat observer berumur panjang berbasis `std::weak_ptr`?
   * *Jawaban:* `std::make_shared` mengalokasikan Managed Object dan Control Block dalam satu potongan memori yang menyatu. Objek dihancurkan saat strong count 0, namun memori fisik blok besar tersebut tidak dapat dibebaskan ke sistem sampai seluruh `weak_ptr` observer mati (weak count 0).
4. **Pertanyaan:** Mengapa Move Constructor wajib diberi spesifikasi `noexcept`?
   * *Jawaban:* Container library standar (seperti `std::vector::reserve` atau `push_back`) memberikan jaminan *Strong Exception Safety*. Jika move constructor suatu tipe data tidak ditandai `noexcept`, vector akan fallback melakukan deep-copy elemen demi elemen saat memicu reallocation array internal guna menjamin data rollback jika exception terlempar.
5. **Pertanyaan:** Apa yang dimaksud dengan *Dangling Pointer*?
   * *Jawaban:* Pointer yang nilainya masih merujuk ke alamat memori fisik yang masa hidupnya (*lifetime*) telah berakhir, dibebaskan (`free`/`delete`), atau stack framenya telah ter-unwind. Mengaksesnya memicu Undefined Behavior.

### Soal Tingkat Menengah (Intermediate)
6. **Pertanyaan:** Jelaskan mekanisme perlindungan idiom *Copy-and-Swap* dalam menjamin *Strong Exception Safety* pada Copy Assignment Operator!
   * *Jawaban:* Idiom ini membuat salinan sementara data melalui copy constructor terlebih dahulu. Jika alokasi salinan gagal (melempar exception), state dari objek target saat ini tidak disentuh sama sekali. Jika berhasil, pertukaran pointer dilakukan menggunakan swap `noexcept`, dan objek sementara tersebut otomatis menghancurkan resource lama dari target saat fungsi berakhir.
7. **Pertanyaan:** Mengapa penggunaan `std::weak_ptr::lock()` diwajibkan sebelum membaca managed object, dan mengapa kita tidak boleh hanya memeriksa `.expired()` lalu langsung membaca objek?
   * *Jawaban:* Memeriksa `.expired()` memicu *Race Condition (TOCTOU: Time of Check to Time of Use)* di lingkungan multithreading. Objek bisa saja dihancurkan oleh thread lain tepat setelah pengecekan `expired()` bernilai false. Method `.lock()` mengeksekusi pemeriksaan dan penambahan strong reference count secara atomik.
8. **Pertanyaan:** Misalkan Anda memiliki array heap yang dibuat dengan `int* arr = new int[100];`. Mengapa memanggil `delete arr;` (tanpa tanda kurung siku) adalah Undefined Behavior fatal?
   * *Jawaban:* Kompilator menyimpan jumlah elemen array pada metadata khusus (*cookie layout*) tepat di sebelum offset awal array. Pemanggilan `delete[]` membaca metadata ini untuk memanggil destruktor sebanyak N-kali dan mengembalikan buffer ukuran array. Pemanggilan `delete` skalar hanya memanggil satu destruktor dan menganggap pointer adalah alokasi tunggal, mengacaukan heap allocator header.
9. **Pertanyaan:** Apa implikasi performa dari operasi *Atomic Reference Counting* pada `std::shared_ptr` di arsitektur CPU multi-core?
   * *Jawaban:* Kenaikan atau penurunan counter memakai instruksi bus atomic (seperti `lock xadd` di x86). Instruksi ini memvalidasi cache-coherency protocols (MESI/MOESI), memaksa invalidasi cache line di semua core CPU lain, mengunci memory pipeline, dan membatasi throughput paralelisme instruksi processor.
10. **Pertanyaan:** Mengapa Placement New memerlukan destruksi manual via `ptr->~T()` dan **bukan** via `delete ptr`?
    * *Jawaban:* Placement new mengonstruksi objek pada buffer memori yang sudah dialokasikan sebelumnya. Menjalankan `delete ptr` akan memicu *heap deallocator* pada alamat yang mungkin berasal dari stack, memory pool, atau static buffer, yang menyebabkan heap corruption crash instan. Maka, hanya fase pemanggilan destructor (`ptr->~T()`) yang boleh dipanggil; pembebasan memorinya dikelola sendiri oleh arena penyedia buffer.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang "Thread-Safe LRU Resource Cache with Automatic Eviction & RAII Pinning"

#### Deskripsi Kebutuhan Proyek:
Anda ditugaskan membangun engine cache lokal berkecepatan tinggi untuk menyimpan objek aset/koneksi berat. Cache harus mengeliminasi memory leakage dan mengimplementasikan resource lifecycle otomatis:

1. **Konstruksi Spesifikasi Kelas:**
   * Bangun template class: `template <typename Key, typename Value> class ResourceLRUCache;`.
   * Cache memiliki kapasitas maksimum tetap (misal: 100 entri).
2. **RAII Handle Pinning Pattern:**
   * Method `acquire(const Key&)` tidak boleh mengembalikan raw pointer atau shared_ptr biasa. Method ini wajib mengembalikan custom RAII wrapper: `ResourceHandle<Value>`.
   * Selama `ResourceHandle` suatu item masih aktif dipegang oleh worker/thread pemanggil, item tersebut **TIDAK BOLEH** di-evict (dihapus) dari memory cache meskipun kapasitas maksimum cache telah terlampaui.
3. **Mekanisme Eviction:**
   * Jika cache penuh, dan ada permintaan item baru, cache mencari item tertua (*Least Recently Used*) yang sedang **tidak memiliki handle aktif** (pin count == 0), menghancurkan item tersebut, dan merebut slotnya.
   * Jika seluruh item sedang di-*pin*, pelemparan exception `CacheExhaustedException` harus terjadi secara deterministik.
4. **Validasi Kualitas Kode:**
   * Nol alokasi mentah (`new`/`delete` manual dilarang; gunakan idiom smart pointer atau vector pre-reserved memory).
   * Seluruh destruktor wajib `noexcept`.
   * Compile project dengan flag `-fsanitize=address,undefined -Wall -Wextra -pedantic` dan buktikan tidak ada leak byte terdeteksi saat eksekusi stresstest multithreading.