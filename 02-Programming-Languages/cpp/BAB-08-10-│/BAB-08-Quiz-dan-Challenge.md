# BAB 08: Quiz, Challenge, & Knowledge Check
**Bab 08: Templates, Generic Programming, & Compile-Time Abstraction**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Two-Phase Name Lookup & Disambiguation Syntax
Jelaskan secara mendalam bagaimana compiler C++ (Clang/GCC) memproses template melalui mekanisme *Two-Phase Name Lookup*. Mengapa *dependent names* memerlukan keyword eksplisit `typename` (contoh: `typename T::iterator`) dan `template` (contoh: `ptr->template convert<int>()`)? Analisis apa yang terjadi pada *Abstract Syntax Tree* (AST) compiler pada Fase 1 (*definition time*) versus Fase 2 (*instantiation time*), dan konsekuensi semantik apa yang terjadi jika salah satu keyword tersebut dihilangkan.

### Soal 1.2: Template Specialization vs. Function Overloading
Analisis perbedaan mekanistik antara *Full Specialization*, *Partial Specialization*, dan *Function Template Overloading*. Mengapa komite standardisasi C++ melarang *partial specialization* pada function template? Bagaimana interaksi antara overload resolution dan eksplisit specialization dapat menghasilkan *subtle bugs* di mana spesialisasi tidak terpanggil sesuai ekspektasi pengembang? Sertakan pola arsitektur alternatif (misalnya memindahkan resolusi ke static member struct) untuk mengatasi limitasi ini.

### Soal 1.3: Mekanisme SFINAE dan Sifat Overload Set
Jelaskan prinsip kerja SFINAE (*Substitution Failure Is Not An Error*) dalam konteks pembentukan *candidate set* selama overload resolution. Pada tahapan spesifik apa substitusi tipe terjadi: apakah sebelum atau sesudah pengecekan *access control* (private/protected) dan penegasan *constraint*? Jelaskan mengapa compiler memperlakukan kesalahan substitusi pada *immediate context* sebagai eliminasi kandidat yang valid, namun memperlakukan kegagalan di luar *immediate context* (misalnya di dalam evaluasi body class atau instantiate nested member) sebagai *hard compiler error*.

### Soal 1.4: C++20 Concepts vs. SFINAE (`std::enable_if`)
Bandingkan secara fundamental mekanisme C++20 Concepts dengan SFINAE berbasis `std::enable_if_t`. Bagaimana *subsumption rules* pada C++20 Constraints bekerja untuk menentukan overload yang "lebih spesifik" tanpa memicu ambiguitas? Analisis dampaknya terhadap efisiensi kompilasi (*compile-time throughput*), konsumsi memori compiler, dan keterbacaan pesan kesalahan (*compiler diagnostic error messages*).

### Soal 1.5: Class Template Argument Deduction (CTAD) & User-Defined Deduction Guides
Bagaimana mekanisme CTAD (diperkenalkan pada C++17 dan disempurnakan pada C++20) mengekstrapolasi parameter template class tanpa instansiasi eksplisit? Jelaskan fungsi teknis dari *explicit deduction guide* dan sebutkan skenario di mana implicit deduction guide gagal mendeteksi tipe yang diinginkan (misalnya alokator dinamis, *forwarding references*, atau array-to-pointer decay).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Code Bloat & Monomorphization Overhead
Proses *monomorphization* pada generic programming menghasilkan duplikasi kode assembly untuk setiap kombinasi tipe konkret. Analisis dampak negatif fenomena ini terhadap *Instruction Cache* (I-Cache L1/L2), footprint biner, dan *link-time optimization* (LTO). Jelaskan teknik arsitektur *template hoisting* / *type-erasure idiom* / *base-class idiomatic pattern* (sebagaimana diterapkan pada implementasi `std::vector<void*>` di masa lalu) untuk menekan *binary code bloat* tanpa mengorbankan type safety.

### Soal 2.2: ODR (One Definition Rule) & Explicit Template Instantiation
Di sistem berskala besar yang terdiri dari puluhan *Translation Units* (TUs), instansiasi template implisit pada header file sering kali menyebabkan duplikasi kompilasi kode identik di setiap objek `.o`, memperlambat fase linking secara masif. Bagaimana sintaks `extern template` (C++11) menghentikan instansiasi implisit? Jelaskan apa bahaya pelanggaran ODR jika parameter template bergantung pada konfigurasi preprosesor macro yang tidak konsisten di antara dua translation unit yang berbeda.

### Soal 2.3: Variadic Templates, Fold Expressions, & Stack Exhaustion
Diberikan parameter pack variadik `Args...`. Bandingkan efisiensi instansiasi antara *recursive template unpacking* berbasis inheritance/overloading dengan C++17 *Fold Expressions* (contoh: `(... + args)`). Mengapa pendekatan rekursif rawan memicu compiler *template instantiation depth limit* (`-ftemplate-depth`) dan ledakan jumlah simbol pada tabel simbol objek ELF/Mach-O?

### Soal 2.4: Non-Type Template Parameters (NTTP) & Linkage Mechanics
C++20 memperluas NTTP sehingga mengizinkan *floating-point types* dan *structural class types*. Jelaskan kriteria matematis/arsitektural yang harus dipenuhi oleh suatu class agar valid sebagai *structural type* pada NTTP (terkait public members, trivial destruction, dan kesetaraan nilai bitwise/operator `==`). Bagaimana compiler dan linker memastikan bahwa dua instansiasi template dengan literal NTTP yang identik dari dua TU berbeda merujuk ke satu entity yang sama di memory map?

### Soal 2.5: Forwarding References & The "Universal Reference Constructor" Bug
Perhatikan constructor template berikut:
```cpp
template <typename T>
class Widget {
public:
    template <typename U>
    explicit Widget(U&& data);
};
```
Mengapa constructor di atas secara agresif menyerap (*shadow*) pemanggilan Copy Constructor standar (`Widget(const Widget&)`) ketika objek non-const dipassing? Analisis fenomena ini dari sudut pandang *Reference Collapsing rules*, *Overload Resolution ranking*, dan berikan solusi proteksinya menggunakan `std::enable_if` atau C++20 `requires` clause.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Compile-Time Bottleneck & Memory Saturation pada High-Frequency Trading Core
Sebuah trading engine ultra-low-latency menggunakan framework serialization compile-time berbasis metaprogramming yang sangat kompleks. Pipeline CI/CD mengalami degradasi parah: waktu kompilasi meningkat dari 4 menit menjadi 58 menit, dan compiler GCC kehabisan memori (*OOM Killed*) pada mesin build server 64GB RAM saat mengompilasi unit testing biner berukuran 1.8 GB.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda menggunakan flag `-ftime-trace` (Clang) atau `-ftime-report` (GCC) untuk mengisolasi bottleneck ekspansi template?
  2. Identifikasi potensi rekursi template yang tidak terbatas atau instansiasi kombinatorial ($O(N^2)$ atau $O(2^N)$ AST nodes).
  3. Rancang strategi refaktorisasi: di mana Anda akan menerapkan `extern template`, mengganti template rekursif dengan C++17 fold expressions / C++20 concepts, dan mengabstraksi fungsionalitas non-dependent ke translation unit non-template (`.cpp`).

### Skenario B: Silent Fallback Bug pada Binary Serialization Framework
Sebuah library jaringan mission-critical memiliki template serialization:
```cpp
template <typename T>
std::enable_if_t<std::is_trivially_copyable_v<T>, void>
serialize(Stream& s, const T& val) {
    s.write_bytes(reinterpret_cast<const char*>(&val), sizeof(T));
}

template <typename T>
std::enable_if_t<!std::is_trivially_copyable_v<T>, void>
serialize(Stream& s, const T& val) {
    val.custom_serialize(s);
}
```
Ketika developer menambahkan field `std::string` ke dalam salah satu struct telemetry yang sebelumnya *trivially copyable*, compiler tiba-tiba gagal mengarahkan ke overload yang benar, atau pada kasus lain ketika struct membungkus pointer mentah, data korup terjadi di level *production* tanpa adanya warning dari compiler saat kompilasi.
* **Pertanyaan Diagnostik:**
  1. Mengapa `std::is_trivially_copyable` tetap bernilai `true` untuk struct yang memegang pointer mentah (*shallow copy*), dan apa implikasi fatalnya saat dikirim عبر network?
  2. Jika tipe struct tidak memiliki method `custom_serialize(s)`, pesan error yang dihasilkan sangat membingungkan dan tidak menunjuk akar masalah. Bagaimana Anda mendesain ulang antarmuka fungsi tersebut menggunakan C++20 `concept` untuk memberikan *contract enforcement* yang deterministik dan *clean failure diagnostic*?

### Skenario C: Abstraksi Hardware vs. Zero-Overhead Telemetry (CRTP vs. Concept vs. Virtual)
Arsitektur firmware satelit memerlukan layer abstraksi untuk antarmuka bus komunikasi (SPI, I2C, CAN). Terdapat tiga proposal arsitektur:
- **Opsi 1:** Dynamic Polymorphism klasik dengan *Abstract Base Class* (`virtual void send(...) = 0`).
- **Opsi 2:** Static Polymorphism menggunakan *Curiously Recurring Template Pattern* (CRTP).
- **Opsi 3:** C++20 *Constrained Generic Interface* menggunakan Concept murni tanpa inheritance.
* **Pertanyaan Diagnostik:**
  1. Berdasarkan metrik determinisme runtime (instruksi execution cycle, pointer dereferencing overhead, inlining optimization) dan keterbatasan ruang ROM/Flash micro-controller, analisis trade-off teknis antara Opsi 1, Opsi 2, dan Opsi 3.
  2. Kapan CRTP menjadi anti-pattern jika dibandingkan dengan C++20 Concept? 
  3. Jika sistem memerlukan kemampuan *hot-swap* driver bus secara dinamis saat runtime (tanpa restart mikroprosesor), mengapa Opsi 2 dan 3 tidak dapat memenuhi kebutuhan tersebut secara murni, dan bagaimana arsitektur hibrida (Type Erasure) dapat menyelesaikan limitasi ini tanpa vtable global?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Compile-Time Type-Safe Event Dispatcher

#### Problem Statement
Arsitektur engine high-performance memerlukan sistem komunikasi *Publish-Subscribe* (Event Bus) yang sepenuhnya type-safe, memiliki *zero runtime heap-allocation* pada jalur kritis (*hot-path*), bebas dari *virtual method dispatch* overhead, dan mampu memvalidasi kontrak payload event secara statis pada saat kompilasi.

#### Requirements
1. **Core Concept Enforcement:**
   - Definisikan C++20 Concept bernama `EventPayload` yang memvalidasi bahwa suatu tipe:
     - Merupakan tipe konkret (*non-abstract*).
     - Bersifat *move-constructible* dan *destructible*.
     - Menyediakan static method unik: `static constexpr std::string_view name() noexcept`.
     - Memiliki ukuran total tidak melebihi 128 byte (`sizeof(E) <= 128`).
2. **Static Event Dispatcher Engine:**
   - Implementasikan class template `StaticDispatcher<MaxSubscribersPerEvent, Events...>` di mana `Events` adalah variadic pack yang telah divalidasi oleh `EventPayload`.
   - Menggunakan *flat fixed-size buffers* internal (misal: array of function pointers / lightweight non-allocating invokers) tanpa memanggil `new` atau menggunakan STL allocator (`std::vector`, `std::function` dilarang keras).
3. **Registration & Dispatch Mechanisms:**
   - Method `subscribe<Event, auto Callable>()` mendaftarkan listener pada saat inisialisasi. 
   - Callable harus compatible dengan signature `void(const Event&)`. Gunakan static introspection / type traits untuk menolak callable yang tidak kompatibel pada saat kompilasi.
   - Method `dispatch(const Event& event)` mengeksekusi seluruh registered callbacks secara inline dengan penalti overhead eksekusi setara dengan array loop fungsi pointer biasa.
4. **Compile-Time Rejection (Static Assertions):**
   - Jika sistem mencoba mem-publish atau subscribe tipe event yang tidak terdaftar di pack `Events...`, compiler harus memunculkan pesan error statis yang eksplisit via `static_assert` yang mudah dibaca.
   - Jika kapasitas `MaxSubscribersPerEvent` terlampaui saat registrasi runtime, sistem harus me-return `bool false` tanpa melakukan undefined behavior.

#### Constraints
- Menggunakan standar C++20 murni.
- *Zero dynamic allocation* (`noexcept` guarantees pada dispatch loop).
- Tidak menggunakan dynamic polymorphism (`virtual`, RTTI/`typeid`, `dynamic_cast` dilarang).
- Kompatibel dengan GCC 11+ dan Clang 13+ dengan flag `-Wall -Wextra -Werror -pedantic`.

#### Expected Output
Biner demonstrasi yang menunjukkan:
1. Registrasi minimal 2 event berbeda (misal: `OrderPlacedEvent`, `OrderCanceledEvent`).
2. Dispatch event berjalan deterministik dengan inline asm / direct call instruction (buktikan nol alokasi).
3. Kode contoh yang gagal kompilasi (dikomentari dengan penjelasan compiler diagnostic) ketika mencoba meregistrasikan tipe non-compliant (misal: struct berukuran > 128 byte atau tidak memiliki static `name()`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme *Two-Phase Lookup* dan pemisahan parsing dependent vs non-dependent names.
- [ ] Aturan deduksi parameter template (*Template Argument Deduction*) dan *Reference Collapsing*.
- [ ] Perbedaan fundamental antara full template specialization, partial specialization, dan function overloading.
- [ ] Prinsip kerja SFINAE pada *immediate context* dan perbedaannya dengan C++20 Concepts.
- [ ] Cara kerja C++20 *Requires Expressions* dan *Subsumption Rules* dalam resolusi ambiguitas constraint.
- [ ] Konsep *Monomorphization* dan implikasinya terhadap *Instruction Cache* serta ukuran biner.
- [ ] Mekanisme kerja CTAD (*Class Template Argument Deduction*) dan cara mendefinisikan *custom deduction guides*.
- [ ] Aturan Non-Type Template Parameters (NTTP) modern untuk tipe data non-integral.

### Saya tidak perlu menghafal:
- [ ] Seluruh implementasi internal struct metaprogramming kuno berbasis `std::integral_constant` warisan C++03/C++98.
- [ ] Sintaks boiler-plate compiler-specific intrinsics untuk type traits (e.g., `__is_trivially_constructible`).
- [ ] Konvensi name mangling spesifik dari Itanium ABI atau MSVC ABI untuk simbol template terinstansiasi.
- [ ] Seluruh mapping tipe meta-programming pada header `<type_traits>` di luar tipe yang fundamental dalam standard library.

### Saya harus bisa melakukan:
- [ ] Menganalisis dan men-debug compiler template backtrace error yang kompleks (ratusan baris) secara cepat hingga ke akar kegagalan substitusi.
- [ ] Menulis generic code yang aman menggunakan C++20 Concepts untuk membatasi tipe data secara elegan tanpa menggunakan `std::enable_if`.
- [ ] Menggunakan `extern template` untuk mengoptimasi waktu build proyek C++ berskala besar.
- [ ] Mencegah *code bloat* dengan memisahkan kode non-dependent ke base class non-template (*template hoisting*).
- [ ] Mengimplementasikan *Perfect Forwarding* secara benar menggunakan `std::forward` tanpa merusak invariant copy/move constructor.
- [ ] Mengukur dan memprofil footprint waktu kompilasi menggunakan tooling seperti Clang `-ftime-trace`.