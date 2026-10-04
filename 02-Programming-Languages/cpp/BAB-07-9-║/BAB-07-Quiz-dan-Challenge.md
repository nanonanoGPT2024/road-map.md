# BAB 07: Quiz, Challenge, & Knowledge Check
**Bab 07: Templates, Generic Programming, & Compile-Time Metaprogramming**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Two-Phase Name Lookup & Disambiguation
Jelaskan secara mendalam mekanisme *Two-Phase Name Lookup* pada kompilasi C++ template. Mengapa compiler mewajibkan penggunaan kata kunci `typename` dan `template` sebagai prefix disambiguasi ketika mengakses entitas di dalam dependensi tipe dependen (*dependent names*), dan apa yang terjadi pada Phase 1 versus Phase 2 jika prefix ini dihilangkan?

### Soal 1.2: Template Specialization vs Function Template Overloading
Analisislah perbedaan mendasar antara *Full Template Specialization*, *Partial Template Specialization*, dan *Function Template Overloading*. Mengapa Komite Standar C++ (dan pakar seperti Herb Sutter) merekomendasikan untuk **tidak pernah** melakukan spesialisasi parsial/penuh pada function template, melainkan lebih memilih overloading atau mendelegasikannya ke class template / static method?

### Soal 1.3: Forwarding References & Perfect Forwarding Mechanics
Bedakan secara teknis antara Rvalue Reference (`Type&&`) dan Forwarding Reference (sebelumnya dikenal sebagai *Universal Reference*, `T&&`). Jelaskan interaksi antara *Reference Collapsing Rules* dan `std::forward<T>` dalam menjaga *value category* (lvalue vs rvalue) dari argumen saat diteruskan melalui rantai fungsi generic.

### Soal 1.4: Evolution of Constraints: SFINAE vs C++20 Concepts
Bandingkan mekanisme pembatasan tipe menggunakan SFINAE (Substitution Failure Is Not An Error) berbasis `std::enable_if_t` / `void_t` dengan C++20 *Concepts & Constraints* (`requires` clause). Analisislah dari perspektif:
1. Beban parsing AST compiler dan instansiasi template.
2. Kejelasan pesan diagnostik saat terjadi kegagalan kompilasi.
3. Aturan subsumpsi (*constraint subsumption*) pada resolusi overload.

### Soal 1.5: Class Template Argument Deduction (CTAD) & User-Defined Deduction Guides
Bagaimana Class Template Argument Deduction (CTAD) bekerja sejak C++17? Dalam skenario apa compiler gagal menyimpulkan tipe template parameter secara otomatis sehingga arsitek perangkat lunak wajib mendefinisikan *explicit deduction guides*, khususnya saat menangani konstruktor yang menerima agregat atau alokator?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Code Bloat & Linker Deduplication (COMDAT / Weak Symbols)
Jelaskan siklus hidup biner dari instansiasi template implisit lintas beberapa Translation Unit (TU). Bagaimana mekanisme link-time deduplication (misalnya via *COMDAT sections* pada ELF/PE) menangani instansiasi identik dari fungsi template? Apa dampak arsitekturalnya terhadap ukuran file biner (*code bloat*), *instruction cache (I-cache) thrashing*, dan bagaimana teknik `extern template` (explicit instantiation declaration) memitigasi masalah ini?

### Soal 2.2: Compile-Time Branching: `if constexpr` vs Tag Dispatching
Ditinjau dari representasi internal compiler (AST generation dan instansiasi tipe):
```cpp
template <typename T>
void process(T val) {
    if constexpr (std::is_integral_v<T>) {
        val.bitwise_manipulation(); // Valid hanya jika T integral
    } else {
        val.normalize();
    }
}
```
Mengapa kode di atas valid dikompilasi untuk tipe floating point (misalnya `double`), padahal `double` tidak memiliki method `bitwise_manipulation()`? Apa perbedaan status *discarded statement* pada `if constexpr` dibandingkan ekspresi branch biasa, dan kondisi apa yang tetap menyebabkan kegagalan kompilasi di dalam blok yang di-*discard*?

### Soal 2.3: Variadic Templates, Recursion, & Fold Expressions
Bandingkan efisiensi kompilasi antara terminasi variadic template klasik berbasis *head-tail recursive instantiations* dengan C++17 *Fold Expressions*. Analisislah limitasi compiler terhadap kedalaman rekursi (`-ftemplate-depth`), jejak memori compiler (*compiler memory footprint*), serta struktur assembly akhir yang dihasilkan oleh kedua pendekatan tersebut.

### Soal 2.4: Non-Type Template Parameters (NTTP) & Type Invariance
Sejak C++20, aturan NTTP diperluas untuk mengizinkan tipe literal kelas (*class types with structural equality*). Jelaskan mekanisme internal compiler memvalidasi kesetaraan struktural NTTP pada level *name mangling*. Mengapa dua instansiasi `Buffer<size_a>` dan `Buffer<size_b>` dianggap sebagai tipe fundamental yang sama sekali berbeda oleh sistem tipe (*type invariance*), dan apa implikasinya terhadap *binary size* dan *interoperability*?

### Soal 2.5: Debugging SFINAE Failures & Compiler Diagnostic Traces
Perhatikan deklarasi template kompleks yang gagal dikompilasi dengan error setebal 200 baris yang melibatkan *nested type traits* dan *substitution failure*. Rancang strategi metodologis untuk mengisolasi kegagalan tersebut tanpa menggunakan debugger eksternal, dengan memanfaatkan teknik:
1. Dead-end static assertion (`static_assert`).
2. Type-printing hack via deliberate incomplete type instantiation.
3. Flag diagnostik compiler modern (misal: `-fconcepts-diagnostics-depth` atau Clang `-Xclang -template-backtrace-limit`).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Compile-Time Explosion & Link-Time OOM pada Trading Gateway
*Konteks:* Sebuah sistem High-Frequency Trading (HFT) core gateway mengalami pembengkakan waktu build dari 4 menit menjadi 1 jam 15 menit, disertai *out-of-memory* (OOM) pada Linker (GNU `ld` / LLVM `lld`) saat mengompilasi rilis *optimized*. Tim arsitek menemukan bahwa library serialisasi pesan internal menggunakan template metaprogramming heavily nested dengan `boost::mp11` atau variadic tuple traversal yang diekspansi secara rekursif di setiap header `.hpp`.

*Pertanyaan Diagnostik:*
1. Metodologi profil kompilasi apa yang harus dijalankan untuk memetakan template mana yang memakan waktu instansiasi dan memori compiler tertinggi (misal via `-ftime-trace` Clang atau MSVC `/bt`)?
2. Bagaimana strategi restrukturisasi dependensi menggunakan `extern template` (explicit instantiation) untuk memaksa instansiasi hanya terjadi pada satu objek TU translasi serialisasi?
3. Modifikasi apa yang perlu diterapkan pada variadic unpack logic agar compiler tidak menghasilkan eksponensial simbol pada tabel relokasi objek (`.o`)?

### Skenario B: Silent Fallback & Overload Hijacking pada Financial Math Engine
*Konteks:* Tim kuantitatif mengimplementasikan pustaka kalkulasi yield obligasi. Terdapat implementasi cepat (*fast-path SIMD*) untuk tipe array teralokasi kontigu dan implementasi lambat (*fallback*) untuk tipe iterator sembarang.
```cpp
template <typename T>
void calculate_yield(T begin, T end); // Fallback: sembarang iterator

template <typename ContiguousIt>
requires std::contiguous_iterator<ContiguousIt>
void calculate_yield(ContiguousIt begin, ContiguousIt end); // Fast SIMD
```
Setelah refactoring ke wrapper iterator baru, sistem produksi secara diam-diam (*silent degradation*) beralih memanggil fungsi fallback tanpa memunculkan compiler error, menyebabkan latensi melonjak 14x lipat tanpa disadari hingga memicu pelanggaran SLA.

*Pertanyaan Diagnostik:*
1. Mengapa compiler lebih memilih fallback template dan mengabaikan versi berkendala (*constrained template*) tanpa menghasilkan error kompilasi sama sekali?
2. Bagaimana cara mengaudit relasi antar-*constraints* menggunakan konsep *Subsumption Rules* C++20 untuk memastikan bahwa jika sebuah iterator gagal memenuhi `std::contiguous_iterator`, kompilasi akan menolak fallback implisit yang tidak diinginkan jika tipe dasarnya adalah pointer?
3. Implementasikan pola proteksi arsitektur (misal *poisoned overload* atau `static_assert` di dalam fallback yang mengevaluasi konsep yang hilang) untuk mencegah terjadinya regresi performa diam-diam semacam ini di masa depan.

### Skenario C: Polymorphism Refactoring: CRTP vs `std::variant` vs Virtual Interfaces
*Konteks:* Anda sedang merancang ulang subsistem Network Packet Parser berkecepatan 100 Gbps. Arsitektur lama berbasis `virtual` method (`IPacketParser` dengan virtual table resolution) menghasilkan overhead dereferensi pointer vptr/vtable dan mencegah compiler melakukan fungsi *inlining*, yang menjadi bottleneck CPU cycle instruction cache miss.
Ada dua proposal arsitektur baru:
- **Proposal 1:** Curiously Recurring Template Pattern (CRTP) untuk static polymorphism.
- **Proposal 2:** `std::variant` yang menampung seluruh kemungkinan tipe paket, diproses melalui `std::visit`.

*Pertanyaan Diagnostik:*
1. Analisislah performa absolut, jejak memori (*memory footprint*), dan kapabilitas CPU branch predictor dari Proposal 1 (CRTP) dibandingkan Proposal 2 (`std::variant` / type-erased jump table).
2. Bagaimana trade-off fleksibilitas kedua pendekatan ini jika sistem harus menangani tipe paket baru yang dimuat via plugin runtime (*dynamic shared object* / `.so`)?
3. Rancanglah prototipe antarmuka berbasis C++20 Concepts yang memungkinkan pemanggilan method parse paket dilakukan secara generik dengan zero-overhead inlining, namun tetap memvalidasi eksistensi interface tanpa penalti runtime vtable.

---

## 4. Chapter Challenge

**Tantangan Praktis: High-Performance Type-Safe Event Dispatcher Berbasis C++20 Concepts & Variadic Metaprogramming**

### Problem Statement
Anda ditugaskan membangun komponen infrastruktur tingkat rendah: **`StaticEventBus`**. Komponen ini berfungsi sebagai tulang punggung komunikasi pesan asinkronus dalam sistem micro-engine game / robotics navigation. Komponen harus mampu mendaftarkan listener untuk event tertentu secara statis, mengeksekusi dispatch pesan dengan jaminan zero-virtualization overhead (tanpa vtable pointer indirection), dan memvalidasi keabsahan struktur pesan pada saat kompilasi (*compile-time contract*).

### Requirements
1. **Event Contract Validation:**
   Gunakan C++20 `concept` bernama `EventConstraint` untuk memastikan tipe event yang dioperasikan:
   - Berupa tipe `struct`/`class` yang `std::is_standard_layout_v` dan `std::is_trivially_copyable_v`.
   - Memiliki method atau member statis `static constexpr uint32_t id()`.
   - Tidak memiliki alokasi memori dinamis di dalamnya.

2. **Zero-Virtualization Handler:**
   - Bangun kelas template `Dispatcher<Events...>` yang menerima daftar seluruh event legal pada saat compile-time via variadic template parameter.
   - Pendaftaran callback handler **tidak boleh** menggunakan `std::function` (karena alokasi memori heap potensial dan overhead indirect function call). Handler harus berupa function pointer mentah atau functor non-allocating.

3. **Compile-Time Safety & Error Propagation:**
   - Jika suatu fungsi memanggil `dispatch(const E& event)` di mana `E` tidak terdapat dalam daftar `Events...` milik `Dispatcher`, compiler **wajib** menolak kompilasi dengan pesan kesalahan deskriptif via `static_assert` yang informatif, bukan cascade error internal STL.

4. **Batch Dispatch Optimization:**
   - Implementasikan method `dispatch_all(const Ts&... events)` menggunakan *C++17 Fold Expressions* untuk mengeksekusi serialisasi eksekusi event beruntun dengan branch minimization.

### Constraints
- Standar bahasa: C++20 murni (menggunakan GCC 11+, Clang 13+, atau MSVC 19.29+).
- Dilarang keras menggunakan `virtual`, `dynamic_cast`, `reinterpret_cast`, atau RTTI (`typeid`).
- Dilarang menggunakan alokasi heap dinamis (`new`, `malloc`, `std::vector`, `std::function`) di dalam hot-path method `dispatch`.
- Compiler warnings harus bersih di bawah `-Wall -Wextra -Wpedantic -Werror`.

### Expected Output
Sediakan file C++ tunggal yang memuat implementasi lengkap:
1. Konsep `EventConstraint`.
2. Struktur data event konkret (contoh: `TickEvent`, `OrderCancelEvent`).
3. Kelas generic `StaticEventBus`.
4. Fungsi `main()` yang mendemonstrasikan:
   - Registrasi listener sukses.
   - Eksekusi `dispatch` dan `dispatch_all`.
   - Pembuktian inspeksi assembly (via komentar/penjelasan kode) bahwa fungsi listener berhasil di-*inline* secara optimal oleh compiler pada optimasi `-O2`/`-O3`.
5. Satu blok kode non-kompilasi yang di-comment out yang memperlihatkan bagaimana `static_assert` menolak event yang melanggar kontrak konsep secara visual.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Aturan *Two-Phase Name Lookup*, perlakuan dependent vs non-dependent names, dan kegunaan kata kunci `typename` serta `template` prefix.
- [ ] Mekanisme *Template Argument Deduction* untuk fungsi dan kelas (CTAD), termasuk cara kerja *deduction guides*.
- [ ] Mekanisme kompilasi C++20 Concepts, clause `requires`, subsumption rules, dan perbandingannya dengan idiom SFINAE klasik (`std::enable_if_t`, `void_t`).
- [ ] Semantik *Forwarding References*, *Reference Collapsing*, dan implementasi internal `std::forward` vs `std::move`.
- [ ] Perbedaan instansiasi template implisit vs eksplisit, mekanika COMDAT linkage, serta implikasi *monomorphization* terhadap binary bloat dan cache-line locality.
- [ ] Evaluasi compile-time via `constexpr`, `consteval`, dan pemangkasan AST melalui `if constexpr`.
- [ ] Pattern arsitektural berbasis template: CRTP, Policy-Based Design, Type Erasure, dan Tag Dispatching.

### Saya tidak perlu menghafal:
- [ ] Seluruh puluhan implementasi metaprogramming primitif di header `<type_traits>` (misal struktur internal variadic `std::tuple_cat`); cukup pahami cara membaca dokumentasi dan menggunakannya.
- [ ] Karakter persis dari mangled name template function pada spesifikasi ABI Itanium atau MSVC.
- [ ] Trik-trik kotor SFINAE C++03/11 lawas yang sudah digantikan secara kanonikal oleh C++20 Concepts dan `if constexpr`.
- [ ] Syntax esoteric spesialisasi partial pointer-to-member function tingkat lanjut yang jarang ditemui di luar compiler development.

### Saya harus bisa melakukan:
- [ ] Menulis generic algorithms dan data structures yang memisahkan storage mechanics dari type constraints secara efisien.
- [ ] Mengonversi kode polimorfisme dinamis runtime (`virtual`) ke static polymorphism berbasis CRTP atau C++20 Concepts untuk jalur kode yang kritis terhadap latensi (*hot-path*).
- [ ] Menganalisis dan men-debug cascade error template yang kompleks menggunakan compiler flags modern serta teknik deliberate compilation failure.
- [ ] Menggunakan C++17 Fold Expressions untuk melakukan agregasi dan pemrosesan parameter pack tanpa biaya rekursi instansiasi.
- [ ] Menerapkan `extern template` untuk mempercepat durasi build proyek C++ skala besar yang mengalami degradasi akibat kompilasi template redundan.