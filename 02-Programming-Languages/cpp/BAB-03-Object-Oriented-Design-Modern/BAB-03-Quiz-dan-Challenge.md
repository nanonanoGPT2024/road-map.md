# BAB 03: Quiz, Challenge, & Knowledge Check
**Bab 03: Pemrograman Berorientasi Objek Lanjut, RAII, & Manajemen Resource Modern (C++17/C++20)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Virtual Table (vtable) & Pointer (vptr) Overhead
Jelaskan secara mendalam bagaimana compiler C++ mengimplementasikan *dynamic dispatch* melalui `vtable` dan `vptr`. Bagaimana keberadaan setidaknya satu fungsi `virtual` memengaruhi ukuran memori (*footprint*) dari sebuah instance kelas, alignment data, dan instruksi mesin saat *method call* terjadi? Bandingkan efisiensi runtime *dynamic dispatch* ini terhadap *static dispatch* via *Curiously Recurring Template Pattern* (CRTP).

### Soal 1.2: Idiom RAII dan Exception Safety Guarantees
Definisikan idiom *Resource Acquisition Is Initialization* (RAII) dan jelaskan korelasinya yang mengikat dengan mekanisme penanganan eksepsi (*stack unwinding*). Uraikan tiga level jaminan keamanan eksepsi (*Basic*, *Strong*, dan *No-throw/No-fail guarantee*) serta jelaskan implementasi RAII apa yang wajib diterapkan agar suatu fungsi dapat menjamin *Strong Exception Guarantee*.

### Soal 1.3: Anatomi Value Categories dan Move Semantics
Sejak C++11, klasifikasi ekspresi diperluas menjadi `lvalue`, `prvalue`, dan `xvalue` (glvalue dan rvalue). Jelaskan perbedaan mendasar antara `std::move` dan `std::forward` dari sudut pandang *type casting*. Mengapa `std::move` tidak melakukan pemindahan data aktual di level instruksi mesin (*assembly*), dan apa yang sebenarnya dilakukan oleh move constructor pada resource heap?

### Soal 1.4: Rule of Zero, Three, dan Five
Jelaskan evolusi dari *Rule of Three* (C++98/03) menuju *Rule of Five* dan *Rule of Zero* (Modern C++). Sebutkan skenario konkret di mana mendeklarasikan sebuah `destructor` kustom secara eksplisit akan secara implisit menonaktifkan (*suppress*) sintesis otomatis dari *move constructor* dan *move assignment operator*, serta jelaskan bahaya degradasi performa yang ditimbulkannya.

### Soal 1.5: Smart Pointer: Semantik Kepemilikan dan Overhead Internal
Bandingkan arsitektur memori antara `std::unique_ptr<T>` dan `std::shared_ptr<T>`. Mengapa `std::unique_ptr` dikategorikan sebagai *zero-cost abstraction* (ketika menggunakan *default deleter*), sedangkan `std::shared_ptr` memiliki overhead alokasi memori tambahan (*Control Block*) dan overhead eksekusi (*atomic reference counting*)? Dalam kondisi apa siklus referensi (*circular reference*) terjadi pada `std::shared_ptr`, dan bagaimana `std::weak_ptr` memecahkannya?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Problem Object Slicing
Perhatikan kode berikut:
```cpp
struct Base {
    int id{1};
    virtual void print() const { std::cout << "Base: " << id << '\n'; }
    virtual ~Base() = default;
};

struct Derived : public Base {
    int extra{2};
    void print() const override { std::cout << "Derived: " << id << ", " << extra << '\n'; }
};

void invoke(Base b) {
    b.print();
}
```
Jelaskan apa yang terjadi pada *memory layout* objek `Derived` saat dipassing ke fungsi `invoke(Base b)`. Mengapa fenomena *object slicing* terjadi, apa akibatnya terhadap `vptr`, dan bagaimana Anda mendesain antarmuka fungsi serta kelas tersebut untuk mencegah *slicing* secara permanen di tingkat *compile-time*?

### Soal 2.2: Virtual Destructor Failure & Undefined Behavior
Diberikan kode polimorfik:
```cpp
class PacketProcessor {
public:
    void* buffer;
    PacketProcessor() { buffer = std::malloc(1024); }
    ~PacketProcessor() { std::free(buffer); } // Non-virtual
};

class EncryptedPacketProcessor : public PacketProcessor {
    EVP_CIPHER_CTX* ctx;
public:
    EncryptedPacketProcessor() { ctx = EVP_CIPHER_CTX_new(); }
    ~EncryptedPacketProcessor() { EVP_CIPHER_CTX_free(ctx); }
};

// Caller:
PacketProcessor* p = new EncryptedPacketProcessor();
delete p;
```
Bedah secara mekanistik apa yang terjadi pada pemanggilan `delete p`. Mengapa standar ISO C++ menyatakan tindakan ini sebagai *Undefined Behavior* (UB)? Komponen memori apa saja yang mengalami kebocoran (*leak*), dan bagaimana compiler menghasilkan instruksi penghancuran objek jika destruktor dideklarasikan `virtual`?

### Soal 2.3: Overhead dan Latensi `dynamic_cast`
Mengapa pemanggilan `dynamic_cast<Derived*>(base_ptr)` pada *downcasting* hierarki polimorfik kompleks (terutama *multiple inheritance* atau *virtual inheritance*) membutuhkan Runtime Type Information (RTTI)? Bagaimana struktur data RTTI ditelusuri oleh runtime C++ (misalnya pada itanium ABI), dan mengapa penggunaannya dilarang pada sistem *low-latency* atau *embedded system*?

### Soal 2.4: Perangkap Move Self-Assignment dan State "Valid but Unspecified"
Diberikan implementasi move assignment kustom berikut:
```cpp
DynamicBuffer& operator=(DynamicBuffer&& other) noexcept {
    delete[] m_data;
    m_data = other.m_data;
    m_size = other.m_size;
    other.m_data = nullptr;
    other.m_size = 0;
    return *this;
}
```
Identifikasi *edge-case* fatal pada kode di atas jika terjadi *self-assignment* (contoh: `a = std::move(a);`). Bagaimana skenario ini menyebabkan *use-after-free* atau memori korup? Apa arti definisi standar C++ bahwa objek yang telah di-move harus berada pada status *"valid but unspecified"*, dan tulis perbaikan implementasi idiom *Copy-and-Swap* atau penanganan `this == &other`.

### Soal 2.5: `std::make_shared` vs `std::shared_ptr<T>(new T)` Trade-Off
Penggunaan `std::make_shared<T>()` menggabungkan alokasi instance `T` dan *Control Block* ke dalam satu blok memori contiguous. Jelaskan keuntungan *cache locality* dari pendekatan ini. Namun, jelaskan pula sisi buruknya (*drawback*) terhadap pelepasan memori ketika objek tersebut direferensikan oleh setidaknya satu `std::weak_ptr` yang masih hidup lama setelah seluruh `std::shared_ptr` musnah.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Bottleneck Throughput pada Core Gateway Jaringan
*Konteks*: Sistem gateway finansial berkecepatan tinggi mengalami degradasi throughput hingga 65% dan kenaikan latency p99 dari 20 mikrosekon ke 850 mikrosekon setelah refactoring kode dari buffer pointer mentah ke arsitektur berbasis Modern C++. Pemantauan profil CPU (*perf report*) menunjukkan lonjakan drastis pada instruksi mesin `LOCK CMPXCHG` dan *cache line bouncing* lintas Core CPU.
*Investigasi*: Tim menemukan bahwa setiap paket data di-wrap ke dalam `std::shared_ptr<Packet>` dan di-pass secara *by-value* ke 8 *worker threads* yang berjalan secara paralel di Core CPU berbeda untuk proses *parsing*, *filtering*, *auditing*, dan *routing*.

1. Mengapa transmisi `std::shared_ptr` secara *by-value* menyebabkan fenomena *atomic contention* dan *false sharing* / *cache thrashing* pada arsitektur multi-core multi-socket?
2. Bagaimana Anda merombak kepemilikan data tersebut menggunakan `std::unique_ptr`, move semantics, atau zero-copy ring buffer tanpa mengorbankan keamanan memori?

### Skenario B: Race Condition dan Memory Corruption pada Thread Pool Asinkron
*Konteks*: Suatu subsistem analitik data mengeksekusi komputasi paralel menggunakan worker pool. Aplikasi mengalami insiden *Segmentation Fault* berkala yang sulit direproduksi pada server produksi (bersifat *intermittent*). Kode bermasalah berhasil diisolasi ke unit berikut:
```cpp
void QueueManager::dispatchJobs() {
    HeavyPayload payload = loadPayloadFromDisk();
    for (int i = 0; i < 10; ++i) {
        m_threadPool.enqueue([&payload, i]() {
            payload.processSubChunk(i);
        });
    }
} // dispatchJobs selesai dieksekusi di sini
```
1. Jelaskan secara tepat *root cause* dari *memory corruption* / *segfault* pada kode di atas dengan meninjau *lifetime* dari variabel `payload` dan *thread execution schedule*.
2. Ubah implementasi closure lambda di atas dengan menerapkan *C++14 generalized lambda capture* dan pemilihan pointer atau transfer kepemilikan yang menjamin integritas data tanpa alokasi ganda (*deep-copy*) yang lambat.

### Skenario C: Arsitektur Plugin Mesin Matching: Dynamic vs Static Polymorphism
*Konteks*: Anda bertindak sebagai Principal Engineer yang mendesain subsistem *Matching Engine Order Execution*. Sistem harus mendukung berbagai modul algoritma eksekusi order (misal: *Iceberg*, *TWAP*, *VWAP*) yang dapat dikonfigurasi saat startup atau compile-time. Tim junior mengusulkan penggunaan hierarki class dengan fungsi `virtual` murni:
```cpp
class ExecutionStrategy {
public:
    virtual void onTick(const MarketData& md) = 0;
    virtual ~ExecutionStrategy() = default;
};
```
Namun, pengujian awal menunjukkan adanya *Branch Target Buffer* (BTB) miss yang signifikan pada CPU saat fungsi `onTick` dipanggil miliaran kali per detik, karena CPU tidak dapat melakukan *inlining* instruksi melalui indirect call via `vptr`.

1. Rancang arsitektur alternatif berbasis **Static Polymorphism** menggunakan CRTP (*Curiously Recurring Template Pattern*) atau `std::variant` dikombinasikan dengan `std::visit` (C++17).
2. Tuliskan perbandingan komprehensif (*trade-off analysis*) yang mencakup:
   - Dampak terhadap *instruction cache* dan *inlining*.
   - Waktu kompilasi (*compile-time* vs *binary bloat*).
   - Fleksibilitas pemuatan plugin secara dinamis via `dlopen`/shared library di runtime.

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi High-Performance Zero-Leak `ArenaString` / Hybrid Vector dengan Rule of Five & Exception Safety

#### Problem Statement
Dalam aplikasi frekuensi tinggi, alokasi heap standar menggunakan `std::string` atau `std::vector` untuk string berukuran kecil hingga menengah menimbulkan fragmentasi memori dan degradasi performa akibat syscall alokasi memori (`malloc`/`free`). Anda diminta untuk merancang dan mengimplementasikan kelas kontainer array dinamis berkinerja tinggi bernama `CustomBuffer` yang menerapkan teknik **Small Buffer Optimization (SBO)** atau **Hybrid Storage**.

Jika data muat dalam buffer internal (misalnya 32 byte), objek tidak boleh melakukan alokasi heap sama sekali. Jika data melebihi 32 byte, objek harus mengalokasikan memori dinamis di heap secara aman.

#### Requirements
1. **Penyimpanan Hibrida (SBO)**:
   - Sediakan internal buffer `char m_stackBuf[32]`.
   - Jika kapasitas $\le 32$, gunakan `m_stackBuf`. Jika $> 32$, alokasikan memori di heap menggunakan `new char[]`.
2. **Kepatuhan Rule of Five**:
   - Implementasikan *Destructor*, *Copy Constructor*, *Copy Assignment Operator*, *Move Constructor*, dan *Move Assignment Operator*.
   - Copying harus menghasilkan *deep copy*.
   - Moving harus mentransfer kepemilikan heap secara *zero-copy*, atau menyalin `m_stackBuf` secara langsung jika data berada pada stack buffer tanpa alokasi baru. Sumber move harus ditinggalkan dalam keadaan valid (*resetted*).
3. **Idiom Copy-and-Swap**:
   - Implementasikan fungsi `friend void swap(CustomBuffer& first, CustomBuffer& second) noexcept` dan gunakan untuk mengimplementasikan assignment operators guna memastikan *Strong Exception Guarantee*.
4. **Metode Akses & Modifikasi**:
   - `void append(const char* data, std::size_t len)`: Mendukung realokasi otomatis jika kapasitas terlampaui.
   - `const char* c_str() const noexcept`: Mengembalikan pointer data valid yang diakhiri null-terminator.
   - `std::size_t size() const noexcept` dan `std::size_t capacity() const noexcept`.
   - `bool is_small() const noexcept`: Mengembalikan `true` jika data disimpan di buffer internal stack.

#### Constraints
- Standard: C++17 atau C++20.
- Dilarang keras menggunakan kontainer STL (`std::vector`, `std::string`, `std::unique_ptr`). Anda harus mengelola memori mentah menggunakan `new[]` dan `delete[]`.
- Wajib bebas dari kebocoran memori (*Memory Leak*) dan *Undefined Behavior* saat dianalisis menggunakan `-fsanitize=address,undefined` (ASan/UBSan) atau Valgrind.
- Move constructor dan move assignment operator wajib bertanda `noexcept`.

#### Expected Output Test Case
Program pengujian minimal harus membuktikan:
```cpp
int main() {
    CustomBuffer small_buf;
    small_buf.append("Hello SBO", 9);
    assert(small_buf.is_small() == true);
    assert(std::strcmp(small_buf.c_str(), "Hello SBO") == 0);

    CustomBuffer large_buf;
    std::string large_str(100, 'X');
    large_buf.append(large_str.c_str(), large_str.size());
    assert(large_buf.is_small() == false);
    assert(large_buf.size() == 100);

    // Test Move Semantics
    CustomBuffer moved_buf = std::move(large_buf);
    assert(moved_buf.is_small() == false);
    assert(moved_buf.size() == 100);
    assert(large_buf.size() == 0); // Source invalidated safely

    // Test Copy & Exception Safety
    CustomBuffer copied_buf;
    copied_buf = moved_buf;
    assert(copied_buf.size() == 100);
    assert(std::strcmp(copied_buf.c_str(), moved_buf.c_str()) == 0);

    std::cout << "All SBO and RAII Rule-of-Five checks passed flawlessly!\n";
    return 0;
}
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme translasi pemanggilan method virtual menjadi pointer dereference bertingkat `this -> vptr -> vtable[index]` dan dampaknya terhadap instruksi jump tak langsung (*indirect branch*).
- [ ] Urutan destruksi objek pada hierarki pewarisan bertingkat: dari kelas anak (*most derived*) ke kelas induk (*base class*).
- [ ] Bahwa eksepsi yang dilempar dari dalam `destructor` saat proses *stack unwinding* aktif akan memicu runtime untuk mengeksekusi `std::terminate()`.
- [ ] Aturan kompilator terkait *implicit generation* dari constructor dan assignment operators (kapan move constructor menjadi implicitly deleted).
- [ ] Perbedaan peruntukan `std::unique_ptr` untuk pemodelan kepemilikan eksklusif versus `std::shared_ptr` untuk kepemilikan terdistribusi.
- [ ] Kapan `dynamic_cast` menghasilkan pointer `nullptr` versus melempar eksepsi `std::bad_cast`.

### Saya tidak perlu menghafal:
- [ ] Algoritma internal ABI spesifik pengurutan index slot vtable yang dihasilkan oleh vendor kompilator tertentu (GCC, Clang, MSVC).
- [ ] Skema *Name Mangling* internal kompilator untuk representasi RTTI dan typeinfo symbol names.
- [ ] Implementasi internal bitwise control block dari `std::shared_ptr` bawaan library libstdc++ atau libc++.

### Saya harus bisa melakukan:
- [ ] Menulis dan mendebug kelas yang mengelola resource mentah menggunakan **Rule of Five** dan idiom **Copy-and-Swap** yang thread-safe dan exception-safe.
- [ ] Mengonversi hierarki polymorphism berbasis `virtual` menjadi static dispatch berbasis CRTP atau `std::variant`/`std::visit` untuk eliminasi overhead indirect call pada *hot-path*.
- [ ] Menggunakan tool diagnosa seperti `AddressSanitizer` (`-fsanitize=address`) dan `LeakSanitizer` untuk melacak *memory leak*, *use-after-free*, dan *double free* akibat destruktor yang cacat.
- [ ] Menggunakan `std::unique_ptr` dengan *custom stateless/stateful deleter* untuk mengontrol siklus hidup file handle (POSIX `fd`), koneksi soket, atau C-API opaque pointers (seperti OpenSSL ctx / FILE*).