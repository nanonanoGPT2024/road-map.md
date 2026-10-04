# BAB 04: Quiz, Challenge, & Knowledge Check
**Bab 04: Manajemen Objek Tingkat Lanjut, RAII, dan Semantik Copy/Move**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Jelaskan siklus hidup (*lifecycle*) objek pada C++ dalam konteks stack vs. heap, dan bagaimana paradigma *Resource Acquisition Is Initialization* (RAII) menjamin determinisme destruksi dibandingkan mekanisme *Garbage Collection* (GC) pada runtime berbasis VM.**
2. **Uraikan perbedaan fundamental antara *Copy Constructor* dan *Copy Assignment Operator*. Dalam kondisi apa compiler menginisialisasi objek baru versus memodifikasi *state* objek yang telah teralokasi, dan mengapa *self-assignment check* krusial pada operator penugasan?**
3. **Apa hakikat teknis dari `std::move`? Buktikan mengapa `std::move` tidak mengeksekusi instruksi pergerakan byte (*zero runtime machine code emission*) secara langsung, melainkan sekadar *unconditional static cast* ke *rvalue reference*.**
4. **Jelaskan relasi dan perbedaan arsitektur antara *Rule of Three*, *Rule of Five*, dan *Rule of Zero*. Kapan sebuah class enterprise wajib menerapkan *Rule of Zero*, dan apa risiko arsitektural jika melanggarnya?**
5. **Jelaskan perbedaan mendasar antara *Shallow Copy* dan *Deep Copy* pada class yang mengelola raw pointer ke dynamic memory. Sertakan analisis memori mengenai ancaman *double free vulnerability* jika pointer diduplikasi secara trivial.**

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Analisis fenomena *Object Slicing* saat sebuah *derived class instance* dioperasikan menggunakan *pass-by-value* ke parameter bertipe *base class*. Bagaimana layout memori dan *virtual table pointer* (`vptr`) tereduksi pada level biner?**
2. **Dalam standard C++17, *Copy Elision* dijamin secara formal melalui mekanisme *Guaranteed Copy Elision* (Prvalue evaluation). Jelaskan perbedaan teknis antara *Named Return Value Optimization* (NRVO) yang bersifat heuristik optimasi compiler dengan *Guaranteed Copy Elision*, serta dampaknya terhadap eksekusi *Move Constructor*.**
3. **Mengapa *Move Constructor* dan *Move Assignment Operator* harus secara eksplisit ditandai dengan spesifikasi `noexcept`? Bedah mekanisme internal `std::vector::resize()` atau `push_back()` saat melakukan reallokasi heap dan bagaimana *type trait* `std::is_nothrow_move_constructible` menentukan penggunaan copy vs. move.**
4. **Perhatikan *snippet* kode buggy berikut:**
   ```cpp
   class NetworkSocket {
       int* socket_fd;
   public:
       NetworkSocket(int fd) : socket_fd(new int(fd)) {}
       ~NetworkSocket() { delete socket_fd; }
       NetworkSocket(NetworkSocket&& other) noexcept {
           this->socket_fd = other.socket_fd;
           // Titik kegagalan logika
       }
       NetworkSocket& operator=(NetworkSocket&& other) noexcept {
           if (this != &other) {
               delete this->socket_fd;
               this->socket_fd = other.socket_fd;
               other.socket_fd = nullptr;
           }
           return *this;
       }
   };
   ```
   Identifikasi *undefined behavior* yang terjadi pada *Move Constructor* di atas jika objek sumber keluar dari *scope*, jelaskan baris instruksi perbaikannya, dan analisis mengapa *Move Assignment* di atas berisiko jika objek tujuan berada dalam *state* tidak terdefinisi sebelum penugasan.
5. **Bedah mekanika internal *Universal Reference* (atau *Forwarding Reference*, `T&&` pada konteks *template argument deduction*) vs. *Rvalue Reference* murni (`Type&&`). Bagaimana *Reference Collapsing Rules* bekerja sama dengan `std::forward<T>` untuk mempertahankan *value category* (lvalue vs. rvalue)?**

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spikes pada Core Matching Engine (High-Frequency Trading)
Dalam subsistem *order matching engine*, throughput transaksi mengalami degradasi parah (*p99 latency spikes* melonjak dari $800\text{ ns}$ ke $1.2\text{ ms}$) setiap kali terjadi lonjakan order buku (*order book depth update*). Hasil profil via `perf record` menunjukkan waktu CPU terkuras pada subrutin `memcpy` dan pemanggilan `malloc`/`free` di dalam loop ingest transaksi.
*   **Pertanyaan Diagnostik:** 
    1. Bagaimana Anda membuktikan bahwa implementasi *event dispatcher* secara tidak sengaja memicu *copy constructor* alih-alih *move semantics* pada payload transaksi (`OrderEvent`)?
    2. Langkah optimasi zero-copy apa yang harus diterapkan pada *interface design* (apakah *pass-by-value* digabung `std::move`, *const lvalue reference*, atau *in-place construction* menggunakan *placement new/monotonic buffer allocator*)?

### Skenario B: *Use-After-Move* & Data Race pada Concurrency Task Pipeline
Sebuah sistem *distributed ledger node* memproses blok transaksi secara asinkron menggunakan *thread pool*. Sebuah *unique transaction packet* (`std::unique_ptr<TxPayload>`) di-dispatch ke worker thread menggunakan *lambda capture*:
```cpp
auto payload = std::make_unique<TxPayload>(/* data */);
thread_pool.enqueue([payload = std::move(payload)]() {
    process_payload(std::move(payload));
});
// Developer menambahkan audit log beberapa baris kemudian:
audit_logger.log_submission(payload->get_hash()); 
```
Saat runtime, node mengalami crash sporadis dengan sinyal `SIGSEGV` (Address Boundary Error), namun crash tersebut tidak konsisten terjadi pada testing lokal.
*   **Pertanyaan Diagnostik:**
    1. Mengapa crash ini terjadi secara deterministik di level kode tetapi sporadis di tingkat eksekusi OS scheduler? 
    2. Apa status legal dari sebuah objek C++ pasca `std::move` (*valid but unspecified state*), dan mengapa dereferensi `payload->get_hash()` di atas adalah *undefined behavior* absolut?
    3. Bagaimana restrukturisasi kode untuk menjamin integritas transfer kepemilikan tanpa membuka celah *use-after-move*?

### Skenario C: Migrasi Legacy Monolith: ABI Incompatibility & RAII Wrapper
Sebuah sistem telekomunikasi berbasis C++03 menggunakan raw pointer OS (`SOCKET`, `FILE*`, `void* mmap_handle`) yang dioperasikan di seluruh lapisan bisnis logic. Tim arsitektur diinstruksikan melakukan refactoring ke modern C++20 tanpa merusak ABI kompatibilitas dengan library pihak ketiga (*pre-compiled C-dynamic library* `.so`).
*   **Pertanyaan Diagnostik:**
    1. Bagaimana Anda merancang generic RAII handle class (`UniqueHandle<T, Deleter>`) tanpa *runtime overhead* (zero abstraction cost) yang kompatibel dengan signature API C lama?
    2. Bagaimana strategi menangani *custom deleter* stateful vs stateless (menggunakan teknik *Empty Base Optimization* / `[[no_unique_address]]`) agar ukuran *smart handle* tetap setara dengan ukuran raw pointer primitif ($8\text{ bytes}$ pada sistem 64-bit)?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Zero-Copy Ring Buffer dengan RAII & Semantik Move Eksplisit

#### Problem Statement
Dalam streaming pipeline performa tinggi, alokasi memori berulang di hot-path merupakan anti-pattern fatal. Anda ditugaskan untuk membangun sebuah kontainer *Circular Ring Buffer* bertipe generik `RingBuffer<T, Capacity>` berbasis fixed-size flat array tanpa memanggil `malloc`/`free` saat proses *push* dan *pop*.

#### Requirements
1. **Memory Allocation:** Memori internal harus menggunakan buffer *uninitialized storage* (`alignas(alignof(T)) std::byte storage[Capacity * sizeof(T)]`) untuk menghindari konstruksi default dari `T` saat buffer diinisialisasi.
2. **Lifecycle Management:** 
   - Elemen baru harus dikonstruksi secara langsung pada storage menggunakan *placement new* via semantik *Perfect Forwarding* (`emplace`).
   - Elemen yang di-pop harus dihancurkan secara eksplisit dengan pemanggilan destruktor manual (`ptr->~T()`).
3. **The Rule of Five Compliance:**
   - Hapus *Copy Constructor* dan *Copy Assignment Operator* (`= delete`).
   - Implementasikan *Move Constructor* dan *Move Assignment Operator* yang menjamin transfer kepemilikan data yang aman antar-buffer, meninggalkan buffer sumber dalam status kosong (*empty state*), ditandai dengan `noexcept`.
4. **Exception Safety:** Berikan garansi *Strong Exception Guarantee* pada operasi `emplace`. Jika konstruksi `T` melempar *exception*, state index ring buffer tidak boleh korup.

#### Constraints
- Menggunakan standar C++20.
- Dilarang keras menggunakan *smart pointers* bawaan (`std::shared_ptr`, `std::unique_ptr`) atau kontainer STL (`std::vector`). Anda harus mengelola raw storage langsung.
- Tidak boleh ada kebocoran memori (*memory leak*) ketika instance `RingBuffer` dihancurkan dalam kondisi masih berisi elemen aktif.

#### Expected Output
Program harus mendemonstrasikan verifikasi ketat melalui class penguji instrumen (`InstrumentedTracker`) yang mencatat log pemanggilan:
- Default constructor
- Param constructor
- Copy constructor (harus 0 kali dipanggil)
- Move constructor
- Destructor

Pada akhir eksekusi, verifikator harus mencetak:
```text
[VERIFICATION COMPLETED]
Active Instances: 0
Total Allocations: 0 (Heap untouched)
Total Moves: N
Total Copies: 0
Result: 100% Zero-Copy RAII Compliance Validated.
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanika layout memori: Stack, Free Store (Heap), BSS, Text, dan bagaimana *stack unwinding* bekerja saat exception dilempar.
- [ ] Paradigma RAII sebagai pondasi determinisme C++ untuk manajemen memori, file descriptor, mutex locks, dan socket.
- [ ] *Value categories* pasca-C++11: perbedaan mendasar antara `lvalue`, `prvalue`, dan `xvalue` (glvalue vs rvalue).
- [ ] Mekanisme kerja `std::move` dan `std::forward` hingga level assembly / generated instructions.
- [ ] Aturan *The Rule of Five* (Destructor, Copy Constructor, Copy Assignment, Move Constructor, Move Assignment) dan *The Rule of Zero*.
- [ ] Konsekuensi teknis omission atribut `noexcept` pada move constructor terhadap optimasi kontainer STL.
- [ ] Fenomena *Object Slicing* dan mengapa polymorphisme memerlukan referensi atau pointer.
- [ ] *Guaranteed Copy Elision* (C++17) dan batas-batas optimalisasi NRVO pada compiler modern (GCC, Clang, MSVC).

### Saya tidak perlu menghafal:
- [ ] Detail algoritma spesifik setiap compiler dalam mengimplementasikan *vtable dispatch table* offsets.
- [ ] Mangling name scheme spesifik vendor (misal: Itanium ABI vs Microsoft ABI).
- [ ] Seluruh implementasi internal STL header files secara verbatim, cukup memahami *invariants* dan *complexity guarantees* standar C++.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis bug *double free*, *dangling pointer*, dan *use-after-move* menggunakan compiler sanitizer (`-fsanitize=address,undefined`).
- [ ] Mengimplementasikan resource wrapper berbasis RAII dengan overhead runtime 0-byte (Zero-Overhead Abstraction).
- [ ] Menggunakan *placement new* dan pemanggilan destruktor eksplisit secara benar untuk sistem memory pool/allocator.
- [ ] Memanfaatkan `static_assert` dan *type traits* (`std::is_nothrow_move_constructible`, `std::is_trivially_copyable`) untuk menegakkan kontrak performa pada compile-time.
- [ ] Menulis class yang mengeksploitasi semantik move secara sempurna guna mengeliminasi operasi deep copy yang tidak perlu pada jalur transmisi data kritis.