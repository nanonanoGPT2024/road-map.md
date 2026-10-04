# SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 02-Programming-Languages
* **Bahasa Pemrograman:** Modern C++ (C++20/C++23)
* **Bab 09:** Low-Level & OS Interaction
* **Modul 01:** Systems Programming
* **Prasyarat:** 
  * C++ Pointers, References, & Memory Layout (Object Lifetime, Alignment, Padding)
  * C++ Concurrency Basics (`std::atomic`, Memory Models, Threading)
  * Arsitektur Komputer Dasar (Virtual Memory, Register CPU, Interrupts, Cache Lines)
* **Target Audience:** Systems Software Engineer, Platform Engineer, Embedded & HFT Developer.
* **Standar ISO/POSIX:** ISO/IEC 14882:2020 (C++20), IEEE Std 1003.1-2017 (POSIX.1-2017), Linux 5.x+ ABI.

---

# SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik memiliki kapabilitas terukur untuk:
1. **Menganalisis Boundary Kernel-User:** Membedakan biaya runtime, context switch, dan alur eksekusi instruksi antara Ring 3 (User Space) dan Ring 0 (Kernel Space).
2. **Mengonstruksi Abstraksi RAII Berkinerja Tinggi:** Membungkus *primitive resources* sistem operasi (File Descriptors, Shared Memory, Memory Maps) ke dalam Modern C++ RAII idiom dengan garansi zero-overhead abstraction.
3. **Mengoperasikan Virtual Memory Subsystem:** Menggunakan sistem pemetaan memori (`mmap`, `madvise`, `mprotect`) secara langsung untuk operasi I/O berkecepatan tinggi tanpa melewati copy buffer runtime C/C++.
4. **Membangun Inter-Process Communication (IPC) Deterministik:** Mengimplementasikan protokol transfer data lintas-proses tanpa kunci (*lock-free single-producer single-consumer*) menggunakan POSIX Shared Memory dan C++ `std::atomic`.
5. **Mengelola Asynchronous Signals Secara Aman:** Mengisolasi penanganan sinyal OS asynchronous dari race conditions dengan menghindari fungsi non-reentrant melalui penggunaan `signalfd` atau *self-pipe tricks*.
6. **Mendiagnosis Latensi Sistem:** Menemukan *bottlenecks*, kegagalan *syscall*, dan pelanggaran memori pada boundary kernel menggunakan instrumentasi Linux (`strace`, `perf`, `/proc`).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam pemrograman aplikasi tingkat tinggi, *hardware* dan sistem operasi adalah ilusi transparan: memori dianggap tak terbatas, alokasi heap dianggap murah, dan *thread* diasumsikan selalu berjalan mulus. 

Dalam **Systems Programming**, ilusi tersebut ditanggalkan. Anda harus mengadopsi mental model berbasis realitas mesin:

1. **Komputer adalah Mesin Finite State Berhirarki:** 
   CPU tidak mengeksekusi instruksi C++ Anda secara terisolasi. CPU bergerak di antara level privilese hardware (x86-64: Ring 3 vs Ring 0; ARM: EL0 vs EL1). Setiap pemanggilan *system call* adalah gangguan terencana (*software interrupt* atau instruksi `SYSCALL`/`SYSENTER`) yang memaksa CPU menyimpan *state*, mengganti pointer tumpukan (*stack switch*), dan menembus batas isolasi kernel.
2. **Memori Adalah Halaman Virtual (Virtual Pages), Bukan Deretan Byte Kontigu:**
   Heap dan Stack bukan entitas fisik. Mereka hanyalah pemetaan virtual memory yang diatur oleh MMU (Memory Management Unit) melalui struktur *multi-level page table*. Mengalokasikan memori sebenarnya meminta OS untuk menandai *Page Table Entries* (PTE). *Cache line* (umumnya 64 bytes) dan *Page Size* (umumnya 4096 bytes) adalah granularitas riil transfer data, bukan ukuran `sizeof(T)`.
3. **Sistem Operasi adalah Kernel Reaktif:**
   Kernel tidak "menjalankan" kode Anda; ia merespons *traps*, *faults*, dan *hardware interrupts*. Tugas programmer sistem adalah meminimalkan gesekan transisi mode antara User-Space dan Kernel-Space, serta mencegah terjadinya *unplanned context switches*.
4. **RAII adalah Penjaga Integritas Kernel Resource:**
   Kernel melacak resource menggunakan *opaque tokens* primitif integer berdimensi global (seperti `int fd`). Hilangnya kepemilikan token ini menimbulkan kebocoran sumber daya OS. Di C++, destruktor objek adalah mekanisme mutlak untuk menjamin penutupan, pelepasan, dan unmapping handle OS secara deterministik.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Transisi User-Space ke Kernel-Space melalui Syscall

Diagram berikut mengilustrasikan transisi kontrol CPU dan pertukaran *execution context* saat sebuah program C++ memanggil IO primitif atau operasi sistem.

```
+-------------------------------------------------------------------------------+
| USER SPACE (Ring 3)                                                           |
|                                                                               |
|   +-----------------------------------------------------------------------+   |
|   | Aplikasi C++ (Application Layer Logic)                                 |   |
|   |   auto n = read_raw(fd, buffer.data(), buffer.size());                |   |
|   +-----------------------------------+-----------------------------------+   |
|                                       |                                       |
|                                       v                                       |
|   +-----------------------------------------------------------------------+   |
|   | POSIX / C Runtime Wrappers (libc / libstdc++)                         |   |
|   |   Move arguments to registers (RDI, RSI, RDX, R10, R8, R9)            |   |
|   |   Load Syscall ID to RAX (e.g., 0x00 for sys_read on x86_64)          |   |
|   +-----------------------------------+-----------------------------------+   |
|                                       |                                       |
|                                       v                                       |
|                          [ Instruksi: SYSCALL ]                               |
+---------------------------------------|---------------------------------------+
                                        | (Hardware Trap: Switch to Ring 0)
                                        | (Save RIP, RFLAGS, switch RSP)
+---------------------------------------v---------------------------------------+
| KERNEL SPACE (Ring 0)                                                         |
|                                                                               |
|   +-----------------------------------------------------------------------+   |
|   | System Call Handler (Entry point: entry_SYSCALL_64)                   |   |
|   |   - Save user registers to Kernel Stack (pt_regs)                     |   |
|   |   - Lookup System Call Dispatch Table: sys_call_table[RAX]             |   |
|   +-----------------------------------+-----------------------------------+   |
|                                       |                                       |
|                                       v                                       |
|   +-----------------------------------------------------------------------+   |
|   | VFS (Virtual File System) & Kernel Subsystems                         |   |
|   |   - Validasi pointer buffer user-space (access_ok)                    |   |
|   |   - Check Page Cache / Disk I/O / Pipe Buffer                         |   |
|   |   - Salin memori (copy_to_user / zero-copy page splice)               |   |
|   +-----------------------------------+-----------------------------------+   |
|                                       |                                       |
|                                       v                                       |
|                          [ Instruksi: SYSRET / IRET ]                         |
|                                       | (Restore user registers & Ring 3)     |
+---------------------------------------|---------------------------------------+
                                        v
+-------------------------------------------------------------------------------+
| USER SPACE (Ring 3) - Melanjutkan eksekusi C++                                |
+-------------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur File Descriptor Table & Kernel Object Table
Dalam POSIX, *file descriptor* (`fd`) hanyalah integer non-negatif. Anatomi internalnya diatur dalam 3 tingkat struktur di kernel:
* **Per-Process Descriptor Table:** Array indeks yang dimiliki oleh proses (`task_struct->files`). Indeks ini adalah integer `fd`. Elemen array menunjuk ke entri di *System-wide Open File Table*.
* **System-wide Open File Table (`struct file`):** Berisi status operasional file: *file offset*, status flags (e.g., `O_NONBLOCK`, `O_SYNC`), reference count, dan pointer ke *V-Node*.
* **V-Node / Inode Table (`struct inode`):** Berisi metadata permanen file di disk: ukuran file, tipe file, permissions, dan pointer ke operasi driver filesystem yang sebenarnya.

Ketika Anda memanggil `dup(fd)` atau `fork()`, kernel hanya menduplikasi entri pada tingkat *Process Descriptor Table*, merujuk ke `struct file` yang sama, dan menaikkan *reference counter*. File baru tertutup secara fisik di disk ketika *reference counter* mencapai 0.

### 2. Anatomi Virtual Address Space (Linux x86_64)
Sistem operasi membagi virtual memory per proses (pada ruang 48-bit addressing canonical) menjadi zona-zona terdefinisi:
* `0x0000000000400000`: Binary `.text` (Instruksi kode biner executable).
* Data Segments: `.data` (Variabel global/static terinisialisasi), `.bss` (Variabel global tak terinisialisasi / *zero-filled*).
* **Heap:** Area pertumbuhan ke atas (alamat bertambah) diatur via `brk()` atau alokator pengguna via `mmap()`.
* **Memory Mapping Segment:** Area alokasi `mmap()` untuk shared libraries (`.so`), IPC shared memory, dan file-backed mappings. Tumbuh ke bawah mendekati heap.
* **Stack:** Tumpukan stack frame thread utama. Tumbuh ke bawah (dari alamat tinggi ke rendah).
* `0x7FFFFFFFFFFF`: Batas akhir User-space.
* `0xFFFF800000000000` s/d `0xFFFFFFFFFFFFFFFF`: Kernel-space memory. Dilindungi proteksi Page Table (CR3 Register). Akses ilegal dari Ring 3 memicu *Hardware Exception 14 (Page Fault -> SIGSEGV)*.

### 3. Siklus Hidup Penanganan Asynchronous Signals
Sinyal adalah *software interrupt* yang diinjeksikan kernel langsung ke thread target:
1. Kernel menandai bit mask pada *pending signal vector* di thread control block (`task_struct->pending`).
2. Sinyal **tidak** dieksekusi secara instan saat bit di-set, melainkan saat thread tersebut hendak beralih dari kernel mode kembali ke user mode (misalnya setelah timer interrupt atau syscall selesai).
3. Kernel menyalin konteks stack user saat itu, memodifikasi register `RIP`/`PC` thread untuk melompat ke alamat *Signal Handler Function* yang didaftarkan via `sigaction`.
4. Handler berjalan di stack pengguna. Jika handler memanggil fungsi yang tidak *Async-Signal-Safe* (misalnya `malloc()`, `std::mutex::lock()`, `printf()`), terjadi kondisi re-entrancy yang merusak struktur data internal libc, memicu *deadlock* fatal atau *heap corruption*.
5. Setelah handler selesai, syscall `sigreturn` dipanggil untuk mengembalikan stack asli dan mengeksekusi instruksi yang tertunda.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. The Cost of System Calls
Pemanggilan `syscall` bukan sekadar *function call* biasa. Pada level mikroarsitektur:
* **Overhead Siklus CPU:** Instruksi `CALL` internal C++ memakan ~1-3 CPU cycles. Instruksi `SYSCALL` memakan ~50-100 cycles murni untuk transisi hardware, belum termasuk logika dispatching kernel.
* **Mitigasi Hardware Meltdown/Spectre (KPTI - Kernel Page Table Isolation):** Jika KPTI aktif, setiap syscall memaksa CPU menukar page table (mereload register `CR3`), menghancurkan validitas *Translation Lookaside Buffer* (TLB). Ini menyebabkan latensi *TLB misses* bertingkat setelah kembali ke user space.
* **vDSO (Virtual Dynamic Shared Object):** Untuk mengurangi beban ini, kernel menyediakan mekanisme vDSO. Fungsi seperti `clock_gettime(CLOCK_MONOTONIC)` tidak lagi melakukan trap ke kernel mode, melainkan membaca memory page yang di-share langsung oleh kernel secara read-only ke memory map proses.

### 2. Direct Memory Mapping (`mmap`) & Zero-Copy I/O
Metode standar `read()` memicu alur transfer ganda:
```
Disk -> Storage Controller DMA -> Kernel Page Cache -> (CPU Copy via copy_to_user) -> Buffer User Space
```
Dengan memanfaatkan `mmap(2)`, aplikasi memetakan halaman kernel page cache secara langsung ke virtual address space proses:
* Alur berubah menjadi:
  ```
  Disk -> Storage Controller DMA -> Kernel Page Cache == (Mapped Directly) == User Virtual Address
  ```
* **Page Faults:** Saat `mmap` dipanggil, memori belum dimuat ke RAM fisik. Memori dialokasikan secara *lazy*. Saat pointer pertama kali dibaca (*read dereference*), CPU mendeteksi *page not present* dan melempar *Minor Page Fault*. Kernel membaca page dari disk atau backing store, mengisi PTE, dan mengeksekusi ulang instruksi pengguna tanpa crash.

### 3. POSIX Shared Memory (`shm_open`) vs Socket IPC
Dalam komunikasi antar-proses:
* **UNIX Domain Sockets / Pipes:** Mengalirkan data melalui kernel buffer. Tetap membutuhkan 2x copy memory (User A -> Kernel, Kernel -> User B) dan minimal 2x context switches untuk sinkronisasi antrean data.
* **POSIX Shared Memory (`shm_open` + `mmap`):** Mengizinkan dua atau lebih proses memetakan *physical frame* RAM yang sama ke dalam virtual memory address space masing-masing. Begitu Proses A menulis data ke alamat memori tersebut, data tersebut secara instan terlihat oleh Proses B pada kecepatan memori bus (*DRAM latency*, nanodetik), sepenuhnya *bypass* kernel ring switch. Sinkronisasi diatur melalui hardware atomics (`std::atomic` dengan `atomic_flag` atau memory barriers).

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL (Step-by-Step)

Berikut adalah implementasi modern C++20 yang menyediakan:
1. Wrapper RAII aman untuk File Descriptor (`UniqueFd`).
2. Wrapper RAII aman untuk Memory Mapped Region (`MappedRegion`).

### File: `system_primitives.hpp`

```cpp
#pragma once

#include <concepts>
#include <cstddef>
#include <fcntl.h>
#include <iostream>
#include <span>
#include <string_view>
#include <sys/mman.h>
#include <sys/stat.h>
#include <system_error>
#include <unistd.h>
#include <utility>

namespace sys {

// RAII wrapper deterministik untuk POSIX file descriptor
class UniqueFd {
public:
    constexpr UniqueFd() noexcept : fd_{-1} {}
    
    explicit UniqueFd(int fd) noexcept : fd_{fd} {}

    ~UniqueFd() noexcept {
        reset();
    }

    // Move-only semantics: mencegah duplikasi kepemilikan handle kernel
    UniqueFd(const UniqueFd&) = delete;
    UniqueFd& operator=(const UniqueFd&) = delete;

    UniqueFd(UniqueFd&& other) noexcept : fd_{other.release()} {}

    UniqueFd& operator=(UniqueFd&& other) noexcept {
        if (this != &other) {
            reset(other.release());
        }
        return *this;
    }

    [[nodiscard]] int get() const noexcept { return fd_; }
    [[nodiscard]] bool valid() const noexcept { return fd_ >= 0; }
    explicit operator bool() const noexcept { return valid(); }

    [[nodiscard]] int release() noexcept {
        return std::exchange(fd_, -1);
    }

    void reset(int new_fd = -1) noexcept {
        if (fd_ >= 0) {
            // close() POSIX syscall tidak boleh diulang jika interrupted (EINTR)
            // pada sistem Linux modern karena FD sudah dibersihkan dari task_struct.
            ::close(fd_);
        }
        fd_ = new_fd;
    }

private:
    int fd_;
};

// RAII wrapper deterministik untuk Memory Mapping POSIX
class MappedRegion {
public:
    MappedRegion() noexcept : data_{MAP_FAILED}, size_{0} {}

    MappedRegion(void* addr, std::size_t length, int prot, int flags, int fd, off_t offset) {
        data_ = ::mmap(addr, length, prot, flags, fd, offset);
        if (data_ == MAP_FAILED) {
            throw std::system_error(errno, std::generic_category(), "mmap failed");
        }
        size_ = length;
    }

    ~MappedRegion() noexcept {
        reset();
    }

    MappedRegion(const MappedRegion&) = delete;
    MappedRegion& operator=(const MappedRegion&) = delete;

    MappedRegion(MappedRegion&& other) noexcept 
        : data_{std::exchange(other.data_, MAP_FAILED)},
          size_{std::exchange(other.size_, 0)} {}

    MappedRegion& operator=(MappedRegion&& other) noexcept {
        if (this != &other) {
            reset();
            data_ = std::exchange(other.data_, MAP_FAILED);
            size_ = std::exchange(other.size_, 0);
        }
        return *this;
    }

    void reset() noexcept {
        if (data_ != MAP_FAILED) {
            ::munmap(data_, size_);
            data_ = MAP_FAILED;
            size_ = 0;
        }
    }

    [[nodiscard]] void* get() const noexcept { return data_; }
    [[nodiscard]] std::size_t size() const noexcept { return size_; }

    template <typename T>
    [[nodiscard]] std::span<T> as_span() const noexcept {
        return std::span<T>{reinterpret_cast<T*>(data_), size_ / sizeof(T)};
    }

private:
    void* data_;
    std::size_t size_;
};

} // namespace sys
```

### File: `main_fundamental.cpp`

```cpp
#include "system_primitives.hpp"
#include <cstring>
#include <iostream>

int main() {
    const char* filename = "test_sys_programming.bin";
    const std::size_t alloc_size = 4096; // 1 Halaman standar OS

    // 1. Membuka file dengan flag O_CLOEXEC (Security Best Practice)
    sys::UniqueFd fd{::open(filename, O_RDWR | O_CREAT | O_TRUNC | O_CLOEXEC, S_IRUSR | S_IWUSR)};
    if (!fd) {
        std::cerr << "Gagal membuka file: " << std::strerror(errno) << '\n';
        return 1;
    }

    // 2. Alokasikan ukuran file via ftruncate
    if (::ftruncate(fd.get(), static_cast<off_t>(alloc_size)) != 0) {
        std::cerr << "Gagal truncate file: " << std::strerror(errno) << '\n';
        return 1;
    }

    // 3. Mapping halaman file ke User Virtual Memory
    try {
        sys::MappedRegion region{nullptr, alloc_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd.get(), 0};

        // 4. Manipulasi buffer melalui C++20 span tanpa overhead IO syscall manual
        auto byte_span = region.as_span<char>();
        const std::string_view payload = "Hello from Modern C++ Systems Programming via Zero-Copy mmap!";
        std::memcpy(byte_span.data(), payload.data(), payload.size());

        // Pastikan dirty pages disinkronkan ke disk
        if (::msync(region.get(), alloc_size, MS_SYNC) != 0) {
            std::cerr << "msync gagal: " << std::strerror(errno) << '\n';
            return 1;
        }

        std::cout << "Data berhasil ditulis ke mmap region. Membaca balik: \n";
        std::cout << std::string_view{byte_span.data(), payload.size()} << '\n';

    } catch (const std::system_error& e) {
        std::cerr << "Exception Sistem Terdeteksi: " << e.what() << " [Code: " << e.code() << "]\n";
        return 1;
    }

    // File descriptor dan mmap region otomatis dibersihkan via RAII saat keluar scope
    ::unlink(filename); // Bersihkan file disk
    return 0;
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Kelas `sys::UniqueFd`
* **Baris 20-21:** `UniqueFd(const UniqueFd&) = delete;`
  Menghapus *copy constructor* dan *copy assignment operator*. Duplikasi linear sebuah integer File Descriptor akan menimbulkan insiden *double-close bug*. Jika thread A menutup FD 3, lalu thread B membuka socket baru yang kebetulan dialokasikan ke FD 3, salinan destruktor lama thread A akan menutup paksa socket milik thread B secara acak (*silent fd corruption*).
* **Baris 27:** `UniqueFd(UniqueFd&& other) noexcept : fd_{other.release()} {}`
  Transfer kepemilikan resource secara eksklusif menggunakan semantik move. `std::exchange` pada baris 40 mengosongkan status object sumber ke `-1`.
* **Baris 46:** `::close(fd_);`
  Mengeksekusi *system call* penutupan file handle OS. Dijalankan hanya jika `fd_ >= 0`. Menggunakan *global scope operator* `::` untuk mengabaikan resolusi lokal dan memanggil fungsi libc murni.

### Analisis Kelas `sys::MappedRegion`
* **Baris 60:** `data_ = ::mmap(addr, length, prot, flags, fd, offset);`
  Mengeksekusi *syscall* `mmap`. Nilai kembalian bukan `nullptr` jika gagal, melainkan konstanta sentinel `MAP_FAILED` (bernilai `reinterpret_cast<void*>(-1)`).
* **Baris 61-63:** Pengecekan kegagalan dengan melemparkan `std::system_error(errno, std::generic_category())`. Pendekatan idiomatik C++ untuk mengonversi error POSIX `errno` thread-local menjadi exception hierarkis C++.
* **Baris 89-94:** `as_span<T>()`
  Memanfaatkan C++20 `std::span` untuk memberikan interface tipe-aman (*type-safe*) yang membungkus pointer mentah *void* dan ukurannya tanpa menyalin alokasi byte data (Zero-Cost Abstraction).

### Analisis Logika Eksekusi File `main`
* **Baris 108:** `O_CLOEXEC`
  Mencegah file descriptor bocor (*leaked*) ke child process jika program memanggil turunan fungsi `execve()`. Bendera ini wajib ada pada setiap operasi `open`/`socket` modern.
* **Baris 115:** `::ftruncate(fd.get(), alloc_size)`
  Ukuran file yang baru dibuat adalah 0 byte. Memetakan file 0 byte via `mmap` dan mencoba mengakses memori tersebut akan memicu *Bus Error (`SIGBUS`)* karena backing physical page tidak eksis pada offset yang diminta. `ftruncate` memicu penambahan metadata ukuran file di kernel inode.
* **Baris 129:** `::msync(region.get(), alloc_size, MS_SYNC)`
  Memaksa kernel melakukan flushing atas *dirty pages* dari cache CPU/RAM ke subsistem persistent storage secara sinkron (`MS_SYNC`).

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Masalah Arsitektur:
Sebuah sistem *High-Frequency Trading* (HFT) menerima ratusan ribu sinyal harga instrumen finansial (*Order Book updates*) per detik melalui interface jaringan berlatensi sub-mikrodetik. 

Sistem log/telemetri analitik terpisah (misalnya proses Python/Go atau proses C++ analitik sekunder) perlu memproses setiap entri sinyal ini secara *real-time* tanpa:
1. Memperlambat proses pengirim (Market Gateway Core) melalui interupsi thread locks/mutexes.
2. Menggunakan sockets loopback TCP/UDP lokal yang memicu overhead context switches dan serialisasi kernel socket buffer.
3. Terkena alokasi dinamis memori di heap (*malloc/new*) pada jalur kritis (*hot path*).

### Solusi Rekayasa Sistem:
Membangun antrean melingkar berbasis memori bersama (**Lock-Free SPSC Inter-Process Shared Memory Ring Buffer**):
* Menggunakan POSIX `shm_open` untuk membuat shared segment di bawah filesystem virtual RAM `/dev/shm`.
* Menggunakan layout data biner murni *Standard Layout Type* (POD - Plain Old Data).
* Menggunakan C++20 `std::atomic` dengan atomics memory orderings (`acquire-release`) yang dialokasikan langsung di dalam shared memory region untuk melacak indeks `head` dan `tail`.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi lengkap, deterministik, dan siap produksi untuk kanal komunikasi Shared Memory SPSC IPC.

### File: `shm_ipc_ringbuffer.hpp`

```cpp
#pragma once

#include <atomic>
#include <concepts>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <new>
#include <span>
#include <string_view>
#include <sys/mman.h>
#include <sys/stat.h>
#include <system_error>
#include <unistd.h>
#include <utility>

namespace ipc {

// Struktur pesan market telemetry POD (Plain Old Data)
struct alignas(64) MarketTick {
    uint64_t timestamp_ns;
    char symbol[8];
    double bid_price;
    double ask_price;
    uint32_t bid_volume;
    uint32_t ask_volume;
    uint32_t sequence_id;
};
static_assert(std::is_trivially_copyable_v<MarketTick>, "MarketTick harus Trivially Copyable");

// Layout Shared Memory Segment
template <typename T, std::size_t Capacity>
requires (std::is_trivially_copyable_v<T> && ((Capacity & (Capacity - 1)) == 0)) // Wajib power-of-two
struct alignas(64) ShmRingBufferLayout {
    // Cache line isolation untuk menghindari False Sharing lintas CPU core
    alignas(64) std::atomic<std::size_t> write_index{0};
    alignas(64) std::atomic<std::size_t> read_index{0};
    alignas(64) T storage[Capacity];
};

template <typename T, std::size_t Capacity>
class ShmSPSCQueue {
public:
    using Layout = ShmRingBufferLayout<T, Capacity>;

    enum class Mode {
        Producer,
        Consumer
    };

    ShmSPSCQueue(std::string_view shm_name, Mode mode) 
        : name_{shm_name}, mode_{mode} 
    {
        const std::size_t total_size = sizeof(Layout);
        
        int flags = (mode == Mode::Producer) 
                    ? (O_RDWR | O_CREAT | O_CLOEXEC) 
                    : (O_RDWR | O_CLOEXEC);

        shm_fd_ = ::shm_open(name_.data(), flags, S_IRUSR | S_IWUSR);
        if (shm_fd_ < 0) {
            throw std::system_error(errno, std::generic_category(), "shm_open gagal");
        }

        if (mode == Mode::Producer) {
            if (::ftruncate(shm_fd_, static_cast<off_t>(total_size)) != 0) {
                ::close(shm_fd_);
                throw std::system_error(errno, std::generic_category(), "ftruncate gagal");
            }
        }

        void* mapped = ::mmap(nullptr, total_size, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd_, 0);
        if (mapped == MAP_FAILED) {
            ::close(shm_fd_);
            throw std::system_error(errno, std::generic_category(), "mmap gagal");
        }

        layout_ = static_cast<Layout*>(mapped);

        if (mode == Mode::Producer) {
            // Placement new untuk menginisialisasi atomic state pada proses pertama
            new (&layout_->write_index) std::atomic<std::size_t>(0);
            new (&layout_->read_index) std::atomic<std::size_t>(0);
        }
    }

    ~ShmSPSCQueue() noexcept {
        if (layout_ != nullptr) {
            ::munmap(layout_, sizeof(Layout));
        }
        if (shm_fd_ >= 0) {
            ::close(shm_fd_);
        }
        // Producer menghapus resource dari kernel namespace saat destruct
        if (mode_ == Mode::Producer) {
            ::shm_unlink(name_.data());
        }
    }

    ShmSPSCQueue(const ShmSPSCQueue&) = delete;
    ShmSPSCQueue& operator=(const ShmSPSCQueue&) = delete;

    // Zero-Copy Enqueue (Khusus Producer)
    bool push(const T& item) noexcept {
        const std::size_t current_write = layout_->write_index.load(std::memory_order_relaxed);
        const std::size_t current_read  = layout_->read_index.load(std::memory_order_acquire);

        // Jika buffer penuh (Full)
        if ((current_write - current_read) >= Capacity) {
            return false;
        }

        // Fast bitwise indexing karena Capacity adalah 2^N
        std::size_t slot = current_write & (Capacity - 1);
        std::memcpy(&layout_->storage[slot], &item, sizeof(T));

        // Rilis data ke Consumer menggunakan memory_order_release
        layout_->write_index.store(current_write + 1, std::memory_order_release);
        return true;
    }

    // Zero-Copy Dequeue (Khusus Consumer)
    bool pop(T& item) noexcept {
        const std::size_t current_read  = layout_->read_index.load(std::memory_order_relaxed);
        const std::size_t current_write = layout_->write_index.load(std::memory_order_acquire);

        // Jika buffer kosong (Empty)
        if (current_read == current_write) {
            return false;
        }

        std::size_t slot = current_read & (Capacity - 1);
        std::memcpy(&item, &layout_->storage[slot], sizeof(T));

        // Rilis slot ke Producer
        layout_->read_index.store(current_read + 1, std::memory_order_release);
        return true;
    }

private:
    std::string_view name_;
    Mode mode_;
    int shm_fd_{-1};
    Layout* layout_{nullptr};
};

} // namespace ipc
```

### File: `producer.cpp`

```cpp
#include "shm_ipc_ringbuffer.hpp"
#include <chrono>
#include <iostream>
#include <thread>

int main() {
    constexpr std::size_t QueueCapacity = 1024; // 2^10
    const char* shm_path = "/hft_order_stream";

    try {
        std::cout << "[Producer] Membuka Shared Memory: " << shm_path << '\n';
        ipc::ShmSPSCQueue<ipc::MarketTick, QueueCapacity> queue{shm_path, ipc::ShmSPSCQueue<ipc::MarketTick, QueueCapacity>::Mode::Producer};

        std::cout << "[Producer] Memulai push data high-throughput...\n";

        for (uint32_t seq = 1; seq <= 500'000; ++seq) {
            ipc::MarketTick tick{
                .timestamp_ns = static_cast<uint64_t>(std::chrono::high_resolution_clock::now().time_since_epoch().count()),
                .symbol = "AAPL",
                .bid_price = 180.25 + (seq % 10),
                .ask_price = 180.30 + (seq % 10),
                .bid_volume = 100u * seq,
                .ask_volume = 150u * seq,
                .sequence_id = seq
            };

            // Spin jika buffer penuh
            while (!queue.push(tick)) {
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause(); // Mencegah CPU pipeline stall pada spin loop
                #endif
            }

            if (seq % 100'000 == 0) {
                std::cout << "[Producer] Terkirim: " << seq << " ticks\n";
            }
        }

        std::cout << "[Producer] Selesai. Menunggu proses consumer selesai sebelum unmap...\n";
        std::this_thread::sleep_for(std::chrono::seconds(2));

    } catch (const std::exception& ex) {
        std::cerr << "[Producer Error] " << ex.what() << '\n';
        return 1;
    }

    return 0;
}
```

### File: `consumer.cpp`

```cpp
#include "shm_ipc_ringbuffer.hpp"
#include <chrono>
#include <iostream>

int main() {
    constexpr std::size_t QueueCapacity = 1024;
    const char* shm_path = "/hft_order_stream";

    try {
        std::cout << "[Consumer] Menghubungkan ke Shared Memory: " << shm_path << '\n';
        ipc::ShmSPSCQueue<ipc::MarketTick, QueueCapacity> queue{shm_path, ipc::ShmSPSCQueue<ipc::MarketTick, QueueCapacity>::Mode::Consumer};

        std::cout << "[Consumer] Mendengarkan event stream...\n";

        uint32_t received = 0;
        ipc::MarketTick tick{};

        while (received < 500'000) {
            if (queue.pop(tick)) {
                ++received;
                if (received % 100'000 == 0) {
                    std::cout << "[Consumer] Diterima Seq: " << tick.sequence_id 
                              << " | Sym: " << tick.symbol 
                              << " | Bid: " << tick.bid_price 
                              << " | Vol: " << tick.bid_volume << '\n';
                }
            } else {
                #if defined(__x86_64__) || defined(_M_X64)
                __builtin_ia32_pause();
                #endif
            }
        }

        std::cout << "[Consumer] Sukses memproses " << received << " ticks tanpa kerugian paket.\n";

    } catch (const std::exception& ex) {
        std::cerr << "[Consumer Error] " << ex.what() << '\n';
        return 1;
    }

    return 0;
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. IPC Mechanisms Comparison

| Metrik / Dimensi | POSIX Shared Memory (`shm_open`) | UNIX Domain Sockets (`AF_UNIX`) | Pipes (`pipe2`) | TCP Loopback (`127.0.0.1`) |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput** | **Maksimal** (~50-100 GB/s, memory bus bound) | Moderat (~2-5 GB/s) | Moderat (~2-4 GB/s) | Rendah (~1-2 GB/s) |
| **Latensi (P99)** | **Sub-mikrodetik (< 100 ns)** | 2.0 - 5.0 mikrodetik | 2.5 - 6.0 mikrodetik | 10.0 - 30.0 mikrodetik |
| **Kernel Switches**| **0** (pada hot path transmisi data) | 2 per transaksi I/O | 2 per transaksi I/O | Banyak (TCP Stack traversal) |
| **Kompleksitas** | Tinggi (Butuh sinkronisasi manual/Atomics) | Rendah (Stream / Datagram POSIX API) | Sangat Rendah | Sangat Rendah |
| **Boundary Safety**| Lemah (Pointer corruption merusak shared mem) | Kuat (Kernel memvalidasi memory isolation) | Kuat | Kuat |

### 2. POSIX I/O: Synchronous vs Memory-Mapped vs Asynchronous

| Fitur | Direct `read()` / `write()` | `mmap()` I/O | Modern `io_uring` |
| :--- | :--- | :--- | :--- |
| **Zero-Copy** | Tidak (Buffer copy User $\leftrightarrow$ Kernel) | **Ya** (Direct Page Table Mapping) | **Ya** (Menggunakan registered buffers) |
| **Overhead Syscall** | Tinggi (1 syscall per block/chunk) | **Rendah** (Hanya initial mapping + Page Faults) | **Sangat Rendah** (Submission via ring buffer) |
| **Memory Pressure**| Rendah (Hanya buffer sementara) | Tinggi (Dapat memakan Virtual Address Space besar) | Terkontrol |
| **Penanganan Error**| Deterministik melalui return value & `errno` | Kompleks (Menghasilkan hardware `SIGBUS` jika file truncate) | Deterministik (Completion Queue Entries) |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Truncation Race & `SIGBUS`
Ketika proses membaca atau menulis memori yang dipetakan oleh `mmap()` melebihi batas fisik file yang sebenarnya di disk (misalnya, proses eksternal memanggil `ftruncate()` untuk mengecilkan file secara diam-diam), kernel tidak bisa memenuhi halaman tersebut melalui *Page Fault handler*. Alih-alih mengembalikan status error kode biasa, CPU mengeksekusi instruksi hardware trap yang mengirimkan sinyal `SIGBUS` (Bus Error) ke proses Anda. Jika `SIGBUS` tidak ditangkap, proses langsung diterminasi secara paksa (*crash* seketika).

### 2. Partial Writes & Interrupted System Calls (`EINTR`)
Pada *blocking* I/O konvensional (misalnya pipa atau socket), panggilan `write(fd, buf, count)` tidak memiliki jaminan bahwa seluruh `count` byte langsung ditulis. Selain itu, jika sebuah sinyal OS diterima thread saat syscall sedang tidur, fungsi dapat berhenti dan mengembalikan nilai `-1` dengan nilai `errno = EINTR`. Kode sistem harus selalu menguji kondisi ini dalam loop rekursif:
```cpp
ssize_t bytes_written = 0;
while (bytes_written < total_bytes) {
    ssize_t res = ::write(fd, buf + bytes_written, total_bytes - bytes_written);
    if (res == -1) {
        if (errno == EINTR) continue; // Syscall terinterupsi sinyal, coba lagi
        throw std::system_error(errno, std::generic_category());
    }
    bytes_written += res;
}
```

### 3. Cache Line False Sharing pada IPC Shared Memory
Jika indeks penulisan (`write_index`) dan indeks pembacaan (`read_index`) dari ring buffer diletakkan bersebelahan di memori tanpa isolasi *alignment*, kedua variabel akan berada dalam satu *cache line* (64 bytes) CPU yang sama. Ketika Core 0 (Producer) memperbarui `write_index`, kontroler *Cache Coherency* hardware CPU (protokol MESI) akan secara paksa membatalkan (*invalidate*) cache line Core 1 (Consumer). Ini menghasilkan fenomena **Cache Thrashing / False Sharing**, menghancurkan performa hingga 90%. Solusinya adalah memberikan padding eksplisit menggunakan `alignas(64)`.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menjalankan Kode Non-Async-Signal-Safe di Signal Handler
* **Anti-Pattern:**
  ```cpp
  void bad_handler(int sig) {
      // FATAL: std::cout dan malloc menggunakan internal locks (mutex).
      // Jika thread terinterupsi saat sedang memegang lock tersebut,
      // pemanggilan fungsi ini akan memicu permanent DEADLOCK.
      std::cout << "Menerima sinyal: " << sig << std::endl;
  }
  ```
* **Solusi Modern:** Gunakan `signalfd(2)` pada Linux untuk mengubah sinyal asynchronous menjadi synchronous file descriptor yang dapat dimonitor via `select`/`poll`/`epoll`, atau gunakan flag atomic type-safe:
  ```cpp
  std::atomic_flag signal_received = ATOMIC_FLAG_INIT;
  void safe_handler(int sig) {
      signal_received.test_and_set(std::memory_order_relaxed);
  }
  ```

### 2. File Descriptor Leak saat `fork()` / `exec()`
* **Anti-Pattern:**
  Membuka file tanpa bendera `O_CLOEXEC`:
  ```cpp
  int fd = ::open("secret.key", O_RDONLY); // BOCOOR: file tetap terbuka di child process jika exec dipanggil
  ```
* **Solusi:**
  Selalu sertakan `O_CLOEXEC` pada flag `open()`, atau gunakan `SOCK_CLOEXEC` saat membuat socket:
  ```cpp
  int fd = ::open("secret.key", O_RDONLY | O_CLOEXEC);
  ```

### 3. Mengabaikan Strict Aliasing Rule saat Reinterpreting Raw Memory
* **Anti-Pattern:**
  ```cpp
  void* mem = get_mmap_pointer();
  uint64_t* val = (uint64_t*)mem; // UB: Berpotensi melanggar Strict Aliasing & Aligment Unaligned Access
  ```
* **Solusi:**
  Gunakan `std::memcpy` atau `std::bit_cast` (C++20). Kompiler modern mengenali idiom `std::memcpy` untuk mengabaikan fungsi call runtime dan mengubahnya langsung menjadi instruksi assembly register tunggal (`mov` register).

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **RAII Mutlak untuk Semua Sumber Daya OS:** Tidak boleh ada pointer atau handle primitif yang dibiarkan "telanjang". Bungkus File Descriptors, Mutex Lock POSIX (`pthread_mutex_t`), Socket, dan Memory Mapped Buffers ke dalam Move-Only RAII wrapper.
2. **Deterministic Error Handling via System Error:** Hindari mencetak teks langsung dengan `perror()`. Ekstrak `errno` sesegera mungkin (karena operasi internal C++ lainnya dapat mengubah `errno`) dan lemparkan sebagai `std::system_error(errno, std::generic_category())`.
3. **Penyelarasan Struktur Data (Memory Alignment):**
   * Gunakan `alignas(64)` untuk pembatas variabel multi-threaded/IPC guna mencocokkan batas L1 Cache Line arsitektur modern (x86_64 dan ARM Cortex).
   * Validasi tipe data transfer IPC menggunakan static assertions:
     ```cpp
     static_assert(std::is_standard_layout_v<T>);
     static_assert(std::is_trivially_copyable_v<T>);
     ```
4. **Alokasi Peringatan Awal Memori (`posix_fallocate`):** Daripada mengandalkan `ftruncate` yang dapat menghasilkan *sparse files* (file dengan lubang tanpa backing blok fisik nyata), gunakan `posix_fallocate(fd, 0, size)`. Fungsi ini memaksa kernel menjamin blok fisik di disk sudah dipesan, mencegah kegagalan alokasi disk di kemudian hari.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Memory Advice (`madvise`)
Beri petunjuk kepada Linux Kernel Page Management subsystem tentang pola akses data memori yang dipetakan via `madvise(2)`:
```cpp
// Beri tahu kernel bahwa buffer akan dibaca secara sekuensial -> Kernel akan agresif melakukan pre-fetching halaman berikutnya (Readahead)
::madvise(region.get(), region.size(), MADV_SEQUENTIAL);

// Beri tahu kernel bahwa halaman ini tidak akan dipakai lagi dalam waktu dekat -> Page Cache dibebaskan seketika
::madvise(region.get(), region.size(), MADV_DONTNEED);

// Alokasikan Anonymous Transparent Huge Pages (THP - 2MB page size alih-alih 4KB) -> Menurunkan TLB misses drastis
::madvise(region.get(), region.size(), MADV_HUGEPAGE);
```

### 2. Lock-Free Atomic Memory Fences pada IPC
Gunakan semantik acquire-release seminimal mungkin. Jangan sembarangan menggunakan `std::memory_order_seq_cst` (default) di dalam loop transmisi throughput tinggi. 
* Operasi tulis (`push`) hanya membutuhkan `memory_order_release` untuk mempublikasikan slot baru ke konsumen.
* Operasi baca (`pop`) hanya membutuhkan `memory_order_acquire` untuk mensinkronisasikan visibilitas slot memori dari produsen.

### 3. Cache Line Prefetching
Pada pengolahan data array sistem berkecepatan tinggi, manfaatkan instruksi prefetch hardware sebelum instruksi pemrosesan CPU dipanggil:
```cpp
__builtin_prefetch(&layout_->storage[next_slot], 0, 3); 
// 0: Read only, 3: Derajat temporal locality maksimal (simpan di L1 Cache)
```

---

# SEKSI 16 — KEAMANAN & HARDENING

1. **Proteksi Hak Akses Berkas (`umask` & Modes):**
   Saat memanggil `shm_open` atau `open` dengan `O_CREAT`, jangan pernah memberikan akses *world-writable* (`0666`). Batasi strict hanya untuk user owner (`S_IRUSR | S_IWUSR` $\rightarrow$ `0600`).
2. **Mitigasi TOCTOU (Time-of-Check to Time-of-Use):**
   Hindari memeriksa file dengan `access()` sebelum memanggil `open()`. Kondisi file dapat diubah oleh attacker (via symlink attack) tepat di antara kedua pemanggilan tersebut. Langsung panggil `open()` dengan flag defensif `O_CREAT | O_EXCL` untuk memastikan operasi atomik.
3. **Pembersihan Residu Memori Rahasia (`mlock`):**
   Memori yang memuat kredensial, enkripsi, atau data sensitif dapat dipindahkan oleh kernel ke partisi Swap di disk (*paging out*), mengekspos rahasia dalam unencrypted storage. Kunci halaman memori tersebut ke RAM fisik menggunakan:
   ```cpp
   if (::mlock(secret_memory_ptr, secret_size) != 0) {
       // Tangani error kegagalan memory locking
   }
   ```
4. **Proteksi Eksekusi Memori:**
   Hindari memetakan memori dengan flag `PROT_EXEC` kecuali Anda sedang menulis JIT compiler engine. Prinsip W^X (*Write XOR Execute*): Jangan pernah membuat mapping yang memiliki atribut `PROT_WRITE` dan `PROT_EXEC` secara simultan guna mencegah eksploitasi buffer overflow code injection.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Tracing Interaksi Kernel dengan `strace`
Jalankan program C++ Anda di bawah utilitas `strace` untuk melihat setiap pemanggilan system call, argumen, return value, dan durasi eksekusinya secara *real-time*:
```bash
strace -T -e trace=openat,mmap,munmap,shm_open,close ./my_systems_app
```
* `-T`: Menampilkan waktu yang dihabiskan CPU di dalam kernel call (dalam hitungan mikrodetik).
* Flag `-e`: Filter syscall relevan untuk mengurangi noise log.

### 2. Inspeksi Virtual Memory Map via `/proc`
Untuk memeriksa apakah pemetaan memori Anda berada pada alignment yang benar dan memiliki proteksi yang tepat:
```bash
cat /proc/<PID>/maps
```
Output representatif:
```
7f2a14200000-7f2a14201000 rw-s 00000000 00:14 123456  /dev/shm/hft_order_stream
```
* Kolom `rw-s`: Memori bersifat Read-Write dan *Shared* (`MAP_SHARED`).

### 3. Profiling Performance & Page Faults via `perf`
Periksa apakah aplikasi memicu terlalu banyak page faults yang menyebabkan latency spikes:
```bash
perf stat -e page-faults,minor-faults,major-faults,context-switches ./my_systems_app
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Syscall Trap:** Perpindahan eksekusi dari Ring 3 (User) ke Ring 0 (Kernel) via instruksi hardware CPU `SYSCALL`. Mahal karena context switch, register save/restore, dan potensi TLB shootdown (KPTI).
* **RAII Over Raw Handles:** Selalu jadikan kepemilikan POSIX Resource eksplisit. Hapus copy capability (`= delete`), izinkan move capability (`noexcept`), panggil cleanup system call pada destructor (`close`, `munmap`).
* **mmap Rules:**
  * Mapping minimum berukuran 1 sistem Page Size (biasanya 4096 bytes / 4KB).
  * Ukuran file backing **wajib** disesuaikan via `ftruncate` / `posix_fallocate` sebelum akses dereference dilakukan untuk mencegah `SIGBUS`.
  * Selalu gunakan `O_CLOEXEC` pada open flags.
* **Lock-Free IPC Atomics:**
  * Gunakan tipe data `std::is_trivially_copyable_v<T> == true`.
  * Pisahkan index baca dan index tulis sejauh minimal 64 bytes (`alignas(64)`) untuk menghindari False Sharing CPU Cache.
  * Terapkan ordering `memory_order_release` saat mempublikasikan payload dan `memory_order_acquire` saat membaca payload.
* **Signal Safety:** Jangan pernah gunakan alokasi memori dinamis (`malloc`/`free`), standard I/O streams (`std::cout`), atau mutex locks di dalam native signal handler. Gunakan `signalfd` atau `std::atomic_flag`.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Pertanyaan:** Apa perbedaan fundamental antara file descriptor `fd` dan pointer instansiasi C++ biasa?
   * *Jawaban:* Pointer C++ menyimpan alamat memori langsung di dalam Virtual Address Space user-space proses. File descriptor hanyalah indeks integer sederhana (token numerik) yang memetakan entri tabel file internal di dalam ruang terlindungi Kernel Space.

2. **Pertanyaan:** Mengapa kelas pembungkus File Descriptor RAII harus menghapus *Copy Constructor* (`UniqueFd(const UniqueFd&) = delete;`)?
   * *Jawaban:* Jika diduplikasi, dua instansiasi objek C++ akan menampung integer indeks descriptor yang sama. Ketika salah satu objek dihancurkan, destruktornya memanggil `close(fd)`. Objek kedua yang masih hidup kini memegang *dangling file descriptor* yang tidak valid atau dapat mereferensikan file milik resource lain yang kebetulan dibuka ulang oleh OS dengan integer yang sama.

3. **Pertanyaan:** Mengapa `mmap` mengembalikan `MAP_FAILED` dan bukan `nullptr` saat mengalami kegagalan mapping?
   * *Jawaban:* Secara historis dan teknis arsitektur, alamat memori virtual `0` (`nullptr`) dapat berupa alamat valid pada beberapa arsitektur tingkat rendah/sistem operasi lama. Oleh karena itu, POSIX mendefinisikan sentinel `MAP_FAILED` yang bernilai `reinterpret_cast<void*>(-1)` sebagai indikator eksplisit kegagalan.

4. **Pertanyaan:** Apa fungsi bendera `O_CLOEXEC` pada pemanggilan sistem `open` atau `shm_open`?
   * *Jawaban:* Bendera ini memastikan bahwa file descriptor secara otomatis ditutup oleh kernel ketika proses memanggil salah satu varian eksekusi proses turunan `execve()`, mencegah kebocoran resource rahasia ke binary executable baru.

5. **Pertanyaan:** Berapa ukuran transfer blok data fisik minimum yang dialokasikan oleh subsistem Linux Virtual Memory?
   * *Jawaban:* Umumnya berukuran 4 Kilobytes (4096 Bytes), setara dengan 1 Halaman Fisik (Page Frame) pada arsitektur x86-64 standar.

---

### Soal Tingkat Menengah (Intermediate)

6. **Pertanyaan:** Perhatikan potongan kode berikut:
   ```cpp
   void handle_signal(int sig) {
       static std::string log_msg = "Signal Received!";
       std::cout << log_msg << std::endl;
   }
   ```
   Sebutkan **dua** alasan fatal mengapa implementasi di atas dapat menyebabkan *undefined behavior* atau *deadlock* total pada sistem operasi POSIX!
   * *Jawaban:*
     1. Objek `std::cout` menggunakan sinkronisasi mutex internal yang tidak bersifat *reentrant*. Jika thread menerima sinyal saat sedang memegang mutex `std::cout` tersebut, pemanggilan `std::cout` di dalam handler akan mencoba mengunci mutex yang sama dan memicu *deadlock* permanen.
     2. Inisialisasi thread-safe dari variabel `static` local dan operasi `std::string` dapat memicu alokasi heap memori (`malloc`). Runtime allocator `malloc` memegang lock pool memori global; jika heap sedang dalam kondisi terkunci saat sinyal diinterupsikan, alokasi baru di handler akan memicu kebuntuan sistem (*deadlock* / *heap corruption*).

7. **Pertanyaan:** Mengapa pemanggilan `madvise` dengan flag `MADV_SEQUENTIAL` dapat mengoptimalkan pembacaan berkas log berukuran masif (ratusan Gigabytes)?
   * *Jawaban:* Bendera tersebut memberi instruksi kepada kernel VFS bahwa pola pembacaan memori akan bersifat maju secara berurutan. Kernel merespons dengan melipatgandakan ukuran *readahead window* (pre-fetching blok disk ke kernel page cache sebelum user code secara fisik menyentuh alamat tersebut) serta segera menandai halaman lama yang sudah dilewati untuk dibersihkan dari RAM fisik.

8. **Pertanyaan:** Apa yang dimaksud dengan *False Sharing* dalam konteks IPC POSIX Shared Memory dan bagaimana cara Modern C++ memitigasinya?
   * *Jawaban:* *False Sharing* terjadi ketika dua variabel berbeda yang diakses secara simultan oleh CPU core yang berlainan (misalnya indeks baca dan tulis) berada di dalam satu segmen 64-byte *Cache Line* yang sama. Setiap pembaruan data memicu invalidasi cache lintas hardware core melalui protokol MESI. Mitigasi di C++ dilakukan dengan menyematkan specifier perataan `alignas(64)` pada masing-masing variabel agar dipaksa berada pada baris cache line terisolasi.

9. **Pertanyaan:** Apa yang terjadi jika proses memetakan file berukuran 100 byte melalui `mmap` dan mencoba menulis data pada offset byte ke-5000?
   * *Jawaban:* Kernel tidak memiliki alokasi blok fisik backing store pada offset tersebut. CPU mendeteksi akses invalid di luar batas file fisik saat pemetaan halaman (MMU Page Fault resolution gagal) dan melemparkan interupsi hardware berupa sinyal `SIGBUS` (*Bus Error*), yang secara default langsung mematikan proses jika tidak ditangani secara khusus.

10. **Pertanyaan:** Mengapa transfer data menggunakan SPSC Ring Buffer berbasis `std::atomic` di atas POSIX Shared Memory jauh lebih efisien dibanding pengiriman melalui Loopback UNIX Domain Socket?
    * *Jawaban:* POSIX Shared Memory memetakan RAM fisik yang sama langsung ke address space kedua proses. Transmisi data tidak melibatkan kernel sama sekali (0 context switches, 0 copy buffer tambahan). UNIX Domain Socket mewajibkan minimal dua kali syscall (`write` dan `read`), dua kali perpindahan user-to-kernel context switch, serta penyalinan memori ganda melalui skema *socket buffer* internal kernel.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek Praktikum:
**High-Speed POSIX Telemetry Daemon dengan Asynchronous Signal Engine via `signalfd`**

### Deskripsi Skenario:
Kembangkan sebuah aplikasi sistem headless (*Daemon/Service*) berkinerja tinggi dalam C++20 yang mencatat detak jantung sistem (*heartbeat telemetry*). Layanan ini harus dapat:
1. Membuka resource POSIX shared memory terproteksi `/telemetry_daemon_shm`.
2. Menerapkan penanganan sinyal OS asynchronous (`SIGINT`, `SIGTERM`, `SIGHUP`) secara elegan tanpa race-condition dengan memanfaatkan Linux `signalfd(2)` API yang dipadukan ke dalam loop polling event (`epoll` atau `poll`).
3. Saat menerima sinyal `SIGHUP`, daemon tidak boleh crash melainkan melakukan *re-opening* dan *syncing* ulang memory map tanpa menghentikan thread utama.
4. Saat menerima `SIGINT`/`SIGTERM`, daemon harus membersihkan memory-mapping, menutup descriptor, memanggil `shm_unlink`, dan keluar secara deterministik dengan status kode `0`.

### Panduan Arsitektur & Langkah Implementasi:
1. **Blokir Sinyal di Level Thread Mask:**
   Gunakan `pthread_sigmask(SIG_BLOCK, &mask, nullptr)` di awal fungsi `main()` sebelum thread apapun terbentuk untuk mencegah kernel memanggil handler default.
2. **Buat Signalfd Wrapper:**
   Panggil `int sfd = signalfd(-1, &mask, SFD_NONBLOCK | SFD_CLOEXEC);`. Bungkus descriptor `sfd` ke dalam kelas `UniqueFd` yang telah dibuat pada Seksi 07.
3. **Mekanisme Polling Loop:**
   Gunakan `poll()` atau `epoll_create1()` untuk memonitor dua events secara terpadu:
   * IO descriptor signal (`sfd`).
   * Interval timer descriptor (`timerfd_create()`) untuk interval heartbeat per 500ms.
4. **Validasi Pembersihan Resource:**
   Pastikan tidak ada resource yang tertinggal di `/dev/shm/` setelah daemon dihentikan dengan memeriksa:
   ```bash
   ls -la /dev/shm/telemetry_daemon_shm
   ```
   Berkas virtual tersebut harus hilang secara otomatis saat proses keluar. Jalankan aplikasi di bawah kendali *Valgrind* atau *AddressSanitizer* untuk memverifikasi nol kebocoran memori atau descriptor:
   ```bash
   g++ -std=c++20 -fsanitize=address,undefined -Wall -Wextra daemon.cpp -o daemon -lrt
   ./daemon
   ```