# BAB 05: Quiz, Challenge, & Knowledge Check
**Bab 05: Pemrograman Berorientasi Objek Lanjutan, Virtual Table Dispatch, & Siklus Hidup Objek (RAII)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi dan Mekanisme Resolusi Virtual Table (`vtable`)
Jelaskan secara komprehensif bagaimana compiler mengimplementasikan *dynamic dispatch* menggunakan `vtable` dan `vptr`. Bagaimana struktur memori suatu *instance* objek yang memiliki setidaknya satu fungsi `virtual`, dan apa implikasinya terhadap ukuran memori (`sizeof`), *data alignment*, serta *padding* objek tersebut pada arsitektur x86-64?

### Soal 1.2: Fenomena *Object Slicing*
Analisis apa yang terjadi pada level memori ketika sebuah objek dari *derived class* di-assign atau di-pass secara *by-value* ke variabel/parameter bertipe *base class*. Mengapa *polymorphic behavior* hilang dalam kondisi ini, dan bagaimana peran *copy constructor* milik *base class* dalam terjadinya *object slicing*?

### Soal 1.3: Urgensi dan Mekanisme *Virtual Destructor*
Mengapa setiap *base class* yang dirancang untuk digunakan secara polimorfik wajib mendeklarasikan destruktor virtual (`virtual ~Base()`)? Jelaskan skenario *Undefined Behavior* (UB) dan kebocoran sumber daya (*resource leak*) yang terjadi pada level heap allocator jika destruktor tidak dideklarasikan `virtual` saat menghapus instansiasi *derived class* melalui *pointer-to-base*.

### Soal 1.4: Invarian Sumber Daya dengan Idiom RAII
Definisikan prinsip *Resource Acquisition Is Initialization* (RAII). Bagaimana interaksi antara RAII, pemanggilan destruktor otomatis saat *stack unwinding*, dan penanganan eksepsi menjamin tidak terjadinya kebocoran memori, *dangling locks*, atau *unclosed file descriptors* bahkan ketika operasi konstruktor turunan melempar eksepsi?

### Soal 1.5: Taksonomi *The Rule of Zero, Three, and Five*
Bandingkan secara presisi kapan seorang software architect harus menerapkan *Rule of Zero*, *Rule of Three*, dan *Rule of Five* pada C++11 ke atas. Jelaskan implikasi spesifik terhadap *compiler-generated special member functions* (copy constructor, copy assignment, move constructor, move assignment, dan destructor) jika salah satu dari fungsi tersebut dideklarasikan secara manual oleh programmer.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: *Multiple Inheritance*, *Diamond Problem*, dan *Virtual Base Table*
Pada *multiple inheritance* yang membentuk konfigurasi *diamond*, bagaimana compiler mengorganisir *memory layout* objek untuk menghindari duplikasi sub-objek *base class* saat menggunakan `virtual inheritance`? Jelaskan peran *virtual base pointer* (`vbptr`), *virtual base table* (`vbtable`), dan bagaimana *offset adjustment* dilakukan pada *pointer `this`* ketika terjadi *upcasting* antar hierarki turunan.

### Soal 2.2: Mekanisme *Devirtualization* dan Implikasi Keyword `final`
Bagaimana compiler modern (seperti GCC dan Clang) melakukan optimasi *devirtualization* untuk mengeliminasi *indirect call overhead* dari pemanggilan fungsi virtual? Jelaskan bagaimana penggunaan specifier `final` pada level kelas atau metode memfasilitasi optimasi ini, serta apa dampaknya terhadap *inlining* dan ukuran *instruction cache* (I-cache).

### Soal 2.3: Root Cause Analisis: `pure virtual method called` Runtime Error
Jelaskan skenario eksekusi kode yang memicu runtime error fatal `pure virtual method called` (atau `R6025` di MSVC). Mengapa pemanggilan fungsi virtual di dalam tubuh konstruktor atau destruktor *base class* tidak mendispatch ke implementasi *derived class*, dan bagaimana status `vptr` objek berubah secara bertahap selama siklus konstruksi dan destruksi objek berlangsung?

### Soal 2.4: *Static Polymorphism* via CRTP vs Dynamic Polymorphism
Bandingkan *Curiously Recurring Template Pattern* (CRTP) dengan polimorfisme berbasis *vtable*. Analisis trade-off performa kedua pendekatan tersebut berdasarkan:
1. *Branch prediction* dan *instruction cache locality*,
2. Fleksibilitas runtime (misalnya: *heterogeneous containers*),
3. *Code bloat* dan waktu kompilasi.

### Soal 2.5: Lifecycle dan `std::launder` pada Explicit Placement New
Ketika sebuah buffer memori yang telah dialokasikan digunakan kembali untuk mengonstruksi objek polimorfik baru yang bertipe sama persis menggunakan *placement new* tanpa mendeallokasi storage aslinya, mengapa optimasi agresif compiler dapat melanggar *strict aliasing* atau mengasumsikan devirtualisasi yang salah terhadap pointer lama? Jelaskan peran intrinsik `std::launder` (C++17) dalam memecahkan masalah ini.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Ekstrem pada Core Engine Transaksi Finansial
Sebuah sistem *matching engine* pasar modal memproses pembaruan harga order menggunakan arsitektur polimorfik berikut:
```cpp
struct OrderHandler {
    virtual void on_tick(const MarketData& md) = 0;
    virtual ~OrderHandler() = default;
};
// Diikuti oleh 40 derived class berbeda (LimitOrder, IcebergOrder, StopLoss, dsb.)
std::vector<OrderHandler*> active_handlers; // Menampung 500,000 pointer objek
```
Pada saat *market volatility* tinggi, *profiler* (Linux `perf`) menunjukkan degradasi performa masif dengan metrik:
* L1 Instruction Cache Misses melonjak hingga 22%,
* Tingginya angka Branch Misprediction pada instruksi pemanggilan `handler->on_tick(md)`.

**Pertanyaan Diagnostik:**
1. Mengapa kombinasi pointer array heterogen dan fungsi virtual menyebabkan malapetaka pada arsitektur CPU *out-of-order execution* dan *branch target buffer* (BTB)?
2. Rancang strategi refaktorisasi arsitektur untuk mengeliminasi pemanggilan *indirect call* tanpa mengorbankan fleksibilitas logika bisnis (Pertimbangkan pendekatan *Data-Oriented Design*, `std::variant` dengan `std::visit`, atau teknik *Type-Indexed Batched Processing*).

---

### Skenario B: Race Condition dan Memory Corruption pada Asynchronous Task Queue
Sebuah sistem terdistribusi memproses komputasi jaringan menggunakan antrean tugas (*task queue*) multithreaded. Pengembang mengimplementasikan pengiriman tugas sebagai berikut:

```cpp
class AsyncTask {
public:
    virtual void execute() { /* baseline work */ }
    virtual ~AsyncTask() = default;
};

class ComputePayload : public AsyncTask {
    std::unique_ptr<LargeMatrix> matrix_;
public:
    ComputePayload(std::unique_ptr<LargeMatrix> m) : matrix_(std::move(m)) {}
    void execute() override { matrix_->compute(); }
};

// Thread Worker Producer:
void enqueue_job(AsyncTask task) { // Bug #1
    std::lock_guard<std::mutex> lock(queue_mutex);
    job_queue.push(task);
}
```
Ketika sistem berjalan di bawah beban tinggi, thread *consumer* sering mengalami crash akibat `SIGSEGV` (*Segmentation Fault*), atau data yang diproses tidak lengkap (*uninitialized matrix*).

**Pertanyaan Diagnostik:**
1. Identifikasi dan jelaskan anomali memori yang terjadi pada fungsi `enqueue_job` di atas. Mengapa kode tersebut dapat lolos kompilasi namun gagal secara destruktif saat runtime?
2. Bagaimana perbaikan desain yang ideal untuk antrean tugas polimorfik asinkron dengan memanfaatkan kepemilikan unik (`std::unique_ptr<AsyncTask>`) dan *move semantics*, sekaligus memastikan penanganan *thread-safety* serta kepemilikan resource yang aman?

---

### Skenario C: Dilema Stabilitas ABI (*Application Binary Interface*) pada Dynamic Plugin Architecture
Anda memimpin arsitektur platform desktop modular berkinerja tinggi. Aplikasi inti memuat modul ekstensi vendor pihak ketiga melalui *dynamic shared library* (`.so` di Linux / `.dll` di Windows) saat runtime. Arsitektur awal menggunakan pure abstract interface C++:

```cpp
struct IDataEngine {
    virtual void process_stream(const char* id, double rate) = 0;
    virtual bool validate_credentials() = 0;
    virtual ~IDataEngine() = default;
};
```
Setelah pembaruan versi minor, tim inti menambahkan fungsi virtual baru di tengah definisi antarmuka:
```cpp
struct IDataEngine {
    virtual void process_stream(const char* id, double rate) = 0;
    virtual void set_priority(int level) = 0; // Penambahan fungsi baru
    virtual bool validate_credentials() = 0;
    virtual ~IDataEngine() = default;
};
```
Akibatnya, seluruh plugin lama pihak ketiga memicu crash instan (*memory corruption/illegal jump instruction*) saat fungsi `validate_credentials()` dipanggil oleh host application.

**Pertanyaan Diagnostik:**
1. Bedah secara mekanistis mengapa penambahan fungsi `virtual` di tengah antarmuka merusak *vtable memory layout* dan mematahkan stabilitas ABI biner yang sudah dikompilasi sebelumnya.
2. Bandingkan dua pola arsitektural untuk menyelesaikan masalah ini secara permanen:
   - Pendekatan antarmuka bergaya COM (*Interface versioning* via *UUID* / *QueryInterface*).
   - Penggunaan *PIMPL Idiom* yang digabungkan dengan antarmuka C murni (*C-ABI boundaries*).

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Heterogeneous Event Bus dengan Hybrid Dispatch & RAII Scoped Connection

#### Problem Statement
Dalam arsitektur *low-latency trading* atau *game engine loop*, *event bus* tradisional yang mengandalkan warisan polimorfik runtime berbasis `std::shared_ptr<IEventListener>` dan `virtual on_event()` menyebabkan overhead penundaan cache, alokasi memori berlebih di heap, dan kesulitan pelacakan siklus hidup subscriber (*dangling listener*). Anda diminta merancang subsistem `EventBus` modern yang aman, instan, deterministik, dan bebas kebocoran memori.

#### Requirements
1. **Pola Polimorfisme Statis/Efisien**: Implementasikan sistem *event handling* yang mampu menangani beragam tipe event heterogen tanpa mengharuskan semua tipe event mewarisi satu *base class* tertentu.
2. **RAII Lifetime Management (`ScopedConnection`)**:
   - Ketika subscriber mendaftar ke `EventBus`, fungsi pendaftaran harus mengembalikan objek `ScopedConnection`.
   - Jika objek `ScopedConnection` keluar dari cakupan (*out of scope* / *destroyed*), listener yang terikat harus secara otomatis terlepas (*unsubscribed*) dari `EventBus` tanpa perlu pemanggilan unregister manual.
   - Objek `ScopedConnection` harus bersifat *move-only* (tidak dapat disalin, tetapi dapat dipindahkan).
3. **Thread Safety**: Registrasi, deregistrasi, dan pemancaran (*publishing*) event harus thread-safe, meminimalkan *contention* (gunakan `std::shared_mutex` atau read-write lock pattern).
4. **Zero Heap Allocation pada Hot-Path**: Pemancaran event (*publishing*) ke semua *registered listeners* tidak boleh melakukan alokasi memori dinamis di heap (`operator new` / `malloc`).

#### Constraints
- Menggunakan standar C++17 atau C++20.
- Dilarang keras menggunakan *raw pointer* kepemilikan atau `reinterpret_cast` liar yang melanggar aturan *strict aliasing*.
- Harus lolos pemeriksaan kebersihan memori: Nol *memory leak* dan nol *undefined behavior* di bawah pengujian AddressSanitizer (`-fsanitize=address,undefined`).

#### Expected Output
1. Implementasi kode lengkap dan mandiri (*header-only* atau modular) yang terdiri dari:
   - Kelas `EventBus`,
   - Kelas `ScopedConnection`,
   - Struktur data internal penampung listener.
2. Kode uji (*driver code*) di dalam `main()` yang mendemonstrasikan:
   - Pengiriman tipe data event konkret (misal: `TradeEvent { int id; double price; }` dan `SystemAlert { int code; const char* msg; }`),
   - Bukti bahwa ketika sebuah `ScopedConnection` hancur, listener tersebut tidak lagi menerima sinyal event berikutnya,
   - Kemampuan *move-construction* dari `ScopedConnection`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Representasi memori konkret dari `vptr` dan `vtable`, termasuk di mana pointer tersebut disisipkan dalam tata letak memori kelas berpolimorfisme.
- [ ] Penalti komputasi dari pemanggilan fungsi virtual: *pointer indirection*, *branch misprediction*, dan hambatan terhadap *compiler inlining*.
- [ ] Mekanisme konstruksi dan destruksi objek hierarkis: mengapa `vptr` dimutasi pada setiap langkah konstruksi dari *base* ke *derived*.
- [ ] Konsekuensi fatal dari *Object Slicing* terhadap integritas polimorfik data.
- [ ] Cara kerja memori pada *Virtual Inheritance* untuk menanggulangi *Diamond Problem*.
- [ ] Prinsip RAII sebagai tulang punggung utama manajemen sumber daya dan eksepsi di C++.
- [ ] Implikasi destruktor non-virtual pada kelas polimorfik ketika objek dihapus melalui *base pointer*.
- [ ] Perbedaan deterministik antara polimorfisme statis (CRTP, `std::variant`) dan polimorfisme dinamis (`virtual`).

### Saya tidak perlu menghafal:
- [ ] Tata letak bit persis dari mangled name fungsi virtual pada spesifikasi ABI tertentu (seperti Itanium ABI vs MSVC ABI).
- [ ] Offset byte spesifik yang dihasilkan oleh compiler tertentu pada padding kelas polimorfik (karena bervariasi bergantung compiler, target arsitektur, dan flag alignment).
- [ ] Seluruh tabel resolusi overload yang kompleks dalam kasus pewarisan multi-tingkat (cukup pahami aturan visibilitas dan *hiding rule* dasar).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengeliminasi kebocoran memori atau crash yang dipicu oleh absennya *virtual destructor*.
- [ ] Mengidentifikasi masalah *object slicing* pada *code review* dan merefaktornya menjadi passing via *smart pointers* (`std::unique_ptr`) atau *references to const*.
- [ ] Memanfaatkan specifier `override` dan `final` secara presisi untuk menjamin keamanan kompilasi dan memaksimalkan potensi optimasi *devirtualization*.
- [ ] Menerapkan *Rule of Five* secara lengkap dan benar ketika kelas mengelola sumber daya mentah (*raw OS resource/handle*).
- [ ] Menggunakan AddressSanitizer (ASan) dan LLDB/GDB untuk menelusuri kerusakan memori akibat kesalahan *lifetime*, destruksi ganda, atau pemanggilan *pure virtual function*.
- [ ] Merekayasa arsitektur sistem yang mengisolasi batas ABI menggunakan idiom *PIMPL* atau antarmuka C murni guna menjaga stabilitas biner antarmuka perangkat lunak.