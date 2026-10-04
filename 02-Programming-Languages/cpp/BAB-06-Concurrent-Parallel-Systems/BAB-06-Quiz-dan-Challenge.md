# BAB 06: Quiz, Challenge, & Knowledge Check
**Bab 06: Value Categories, Move Semantics, & Perfect Forwarding**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Taksonomi Value Categories (C++11 hingga C++20)
Jelaskan pohon taksonomi ekspresi dalam C++ modern yang membedakan **glvalue**, **lvalue**, **rvalue**, **prvalue**, dan **xvalue**. Berikan definisi formal berdasarkan dua karakteristik ortogonal: *has identity* (memiliki identitas alamat memori) dan *can be moved from* (dapat dipindahkan sumber dayanya). Sertakan contoh ekspresi kode minimal untuk masing-masing kategori: `lvalue`, `prvalue`, dan `xvalue`.

### Soal 1.2: Mekanisme Kompilasi `std::move`
Banyak pengembang pemula mengasumsikan bahwa `std::move` mengeksekusi operasi pemindahan memori (seperti `memcpy` atau dereferensiasi pointer) pada saat *runtime*. Bedah implementasi internal `std::move` dalam *Standard Template Library* (STL), jelaskan perannya di level *type system* dan *compile-time casting*, serta buktikan mengapa pernyataan "pemanggilan `std::move` menghasilkan *zero runtime overhead*" adalah benar secara arsitektural.

### Soal 1.3: Semantik Status "Moved-From"
Standar ISO C++ menyatakan bahwa objek yang telah menjadi sumber dari operasi move konstruksi atau move assignment berada dalam status *"valid but unspecified state"* (kecuali dijamin lain oleh spesifikasi tipe, seperti `std::unique_ptr` yang dijamin menjadi `nullptr`). Jelaskan apa konsekuensi hukum invarian kelas terhadap status ini, operasi apa saja yang legal dan ilegal dilakukan terhadap objek *moved-from*, serta mengapa destruktor objek *moved-from* tetap wajib dieksekusi saat keluar dari *scope*.

### Soal 1.4: RVO, NRVO, dan Implikasi Pemanggilan `std::move` pada Return Statement
Jelaskan perbedaan mekanis antara *Named Return Value Optimization* (NRVO) dan *prvalue copy elision* (mandatory RVO sejak C++17). Mengapa penulisan kode seperti `return std::move(local_var);` di dalam fungsi yang mengembalikan objek berdasarkan nilai (*by-value*) justru dianggap sebagai sebuah *anti-pattern* performa yang melumpuhkan optimasi kompilator?

### Soal 1.5: Aturan Binding Rvalue Reference (`T&&`)
Tinjau aturan konversi dan pembatasan *binding* referensi dalam C++. Mengapa sebuah rvalue reference (`T&&`) hanya dapat mengikat ekspresi *rvalue* dan menolak ekspresi *lvalue* secara eksplisit? Jika sebuah variabel dideklarasikan sebagai `T&& x = Func();`, jelaskan mengapa ekspresi variabel `x` itu sendiri dievaluasi sebagai sebuah *lvalue* dalam ekspresi berikutnya, bukan *rvalue*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Reference Collapsing Rules & Forwarding Reference
Bedah aturan *Reference Collapsing* yang diterapkan kompilator ketika tipe referensi bertemu dengan substitusi *template deduction* atau alias `typedef`/`using`. Mengapa deklarasi `auto&&` atau `T&&` dalam konteks *template argument deduction* diklasifikasikan sebagai *Forwarding Reference* (Universal Reference), sedangkan `std::vector<T>&&` atau `const T&&` tidak? Tunjukkan matriks kombinasi referensi:
- `&` bertemu `&`
- `&` bertemu `&&`
- `&&` bertemu `&`
- `&&` bertemu `&&`

### Soal 2.2: Anatomi dan Dekonstruksi `std::forward<T>`
Berikut adalah implementasi generik konseptual dari `std::forward`:
```cpp
template <typename T>
constexpr T&& forward(std::remove_reference_t<T>& param) noexcept {
    return static_cast<T&&>(param);
}

template <typename T>
constexpr T&& forward(std::remove_reference_t<T>&& param) noexcept {
    static_assert(!std::is_lvalue_reference<T>::value, "Invalid lvalue to rvalue forwarding");
    return static_cast<T&&>(param);
}
```
Lakukan *trace* langkah demi langkah terhadap proses deduksi tipe dan *casting* saat fungsi target menerima:
1. Argumen *lvalue* dari tipe `MyClass&`
2. Argumen *rvalue* dari tipe `MyClass`
Jelaskan bahaya fatal yang dicegah oleh overload kedua (`remove_reference_t<T>&&`).

### Soal 2.3: Interaksi Krusial `noexcept` Move Constructor dengan Kontainer STL
Ketika `std::vector<T>::push_back` atau `emplace_back` memicu reallokasi kapasitas internal memori, kontainer tersebut wajib menjaga garansi exception yang kuat (*strong exception safety guarantee*). Jelaskan bagaimana utilitas `std::move_if_noexcept` bekerja di balik layar, dan apa konsekuensi drastis terhadap performa alokasi memori jika move constructor kelas buatan Anda tidak didekorasi dengan penanda `noexcept`.

### Soal 2.4: Diagnostik Double-Move dan Silent State Corruption
Periksa kode berikut dan identifikasi cacat logika yang terjadi:
```cpp
struct Packet {
    std::string header;
    std::vector<uint8_t> payload;
};

class NetworkDispatcher {
public:
    void dispatch(Packet p) {
        log_packet(std::move(p));
        send_to_socket(std::move(p));
    }
private:
    void log_packet(Packet p) { /* Mengonsumsi dan menyimpan log */ }
    void send_to_socket(Packet p) { /* Menulis payload ke file descriptor */ }
};
```
Jelaskan mengapa kode ini dapat lolos kompilasi tanpa peringatan eror sintaks, apa status aktual objek `p` saat masuk ke dalam `send_to_socket`, dan bagaimana cara mendesain ulang antarmuka fungsi tersebut untuk mencegah eksploitasi atau *silent runtime bugs* serupa.

### Soal 2.5: Object Slicing dalam Konteks Move Semantics
Jika Anda memiliki hierarki pewarisan polimorfik:
```cpp
class Base {
    std::unique_ptr<ResourceA> res_a;
public:
    Base(Base&&) noexcept = default;
    Base& operator=(Base&&) noexcept = default;
};

class Derived : public Base {
    std::unique_ptr<ResourceB> res_b;
public:
    Derived(Derived&& other) noexcept 
        : Base(other), // BUG!
          res_b(std::move(other.res_b)) {}
};
```
Jelaskan secara presisi apa *bug* struktural pada konstruktor move kelas `Derived` di atas, mengapa kompilator mungkin mengabaikan move semantik pada sub-objek `Base`, dan bagaimana implementasi kanonikal yang tepat untuk memindahkan basis kelas dan anggotanya.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spikes Parah pada High-Frequency Trading (HFT) Engine
* **Konteks:** Sistem *Order Matching Engine* terdistribusi mengalami lonjakan latensi (*latency spike*) p99 dari $1.2\,\mu\text{s}$ melonjak menjadi $140\,\mu\text{s}$ secara sporadis saat volume transaksi pasar melonjak tajam.
* **Investigasi Sistem:** Profiling dengan instrumen CPU performance counter (`perf record`) menunjukkan utilisasi tinggi pada instruksi `memcpy` dan pemanggilan `malloc`/`operator new` yang terkonsentrasi di dalam rutin `std::vector<OrderBookEntry>::emplace_back`.
* **Snippet Kode Terkait:**
```cpp
struct OrderBookEntry {
    uint64_t order_id;
    double price;
    uint32_t quantity;
    std::string client_notes; // Alokasi dinamis jika > 15 chars (SSO limit)

    OrderBookEntry(OrderBookEntry&& other) {
        order_id = other.order_id;
        price = other.price;
        quantity = other.quantity;
        client_notes = std::move(other.client_notes);
    }
    // Copy constructor didefinisikan untuk keperluan audit logging
    OrderBookEntry(const OrderBookEntry& other) = default;
};
```
* **Pertanyaan Diagnostik:**
  1. Identifikasi secara tepat akar penyebab mengapa `std::vector` mengeksekusi operasi copy alih-alih move saat reallokasi array dinamis internal.
  2. Jelaskan perbaikan kode minimal yang wajib dilakukan pada struct `OrderBookEntry` untuk menghilangkan overhead alokasi memori saat reallokasi vector.
  3. Mengapa penambahan keyword spesifik tersebut dapat memulihkan determinisme latensi pada mesin eksekusi tersebut?

---

### Skenario B: Race Condition dan Use-After-Move pada Async Task Dispatcher
* **Konteks:** Sebuah microservice streaming video memproses transkripsi *audio frame* secara paralel menggunakan *thread pool* berbasis coroutine/task queue. Pada kondisi beban tinggi, service mengalami *crash* berkala dengan sinyal `SIGSEGV` (Segmentation Fault) akibat *null-pointer dereference*.
* **Snippet Kode Terkait:**
```cpp
class AudioPipeline {
public:
    template <typename Handler>
    void process_frame(std::unique_ptr<AudioBuffer> buffer, Handler&& handler) {
        auto task = [buf = std::move(buffer), h = std::forward<Handler>(handler)]() mutable {
            if (buf->is_priority()) {
                fast_lane_worker.enqueue([b = std::move(buf)]() {
                    b->process_instant();
                });
            }
            // Background telemetry recording
            telemetry_worker.enqueue([b = std::move(buf)]() {
                b->collect_metrics();
            });
        };
        task_pool.submit(std::move(task));
    }
};
```
* **Pertanyaan Diagnostik:**
  1. Tunjukkan baris kode yang memicu *undefined behavior* dan jelaskan bagaimana objek `buf` diakses setelah kepemilikannya dipindahkan (*use-after-move*).
  2. Mengapa kompilator tidak mengeluarkan peringatan kompilasi ketika closure lambda kedua melakukan *capture move* terhadap `buf` yang mungkin telah berstatus *moved-from*?
  3. Desain ulang implementasi metode `process_frame` tersebut menggunakan idiom kepemilikan yang aman (misalnya: rekonstruksi alur transfer data, pemisahan dependensi, atau penyesuaian tipe smart pointer) tanpa mengorbankan performa *zero-copy*.

---

### Skenario C: Keputusan Arsitektur Desain API Parameter Input
* **Konteks:** Tim infrastruktur inti sedang mendesain ulang pustaka *Middleware Configuration Manager* yang digunakan oleh ratusan komponen microservices. Terdapat perdebatan teknis sengit antara arsitek mengenai penulisan metode mutator/setter untuk string konfigurasi:
  * **Opsi 1 (Overloading):**
    ```cpp
    void set_route(const std::string& route);
    void set_route(std::string&& route);
    ```
  * **Opsi 2 (Pass-by-value and move):**
    ```cpp
    void set_route(std::string route); // Menggunakan std::move(route) di dalam body
    ```
  * **Opsi 3 (Perfect Forwarding Template):**
    ```cpp
    template <typename T>
    requires std::is_constructible_v<std::string, T>
    void set_route(T&& route);
    ```
* **Pertanyaan Diagnostik:**
  1. Bedah trade-off performa (jumlah operasi copy dan move) untuk masing-masing opsi pada saat parameter dipanggil dengan: (a) *lvalue string*, (b) *rvalue string*, dan (c) *string literal* `const char*`.
  2. Tinjau dampak *code bloat*, waktu kompilasi, kebersihan antarmuka publik (kemudahan dibaca pengguna pustaka), serta *binary compatibility* (ABI).
  3. Rekomendasikan opsi terbaik yang harus dipilih tim infrastruktur, lengkap dengan basis rasional teknisnya.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Move-Only Task System (`AnyMoveTask`)

#### Problem Statement
Pustaka standar `std::function` mewajibkan tipe target dapat disalin (*CopyConstructible*). Konsekuensinya, `std::function` **tidak dapat membungkus** objek move-only seperti lambda yang meng-capture `std::unique_ptr`, `std::promise`, atau *OS handle* (seperti `SocketDescriptor`). Anda diminta merancang dan mengimplementasikan kelas `AnyMoveTask` kustom yang bersifat *move-only*, bebas alokasi memori berlebih (*Small Buffer Optimization* / SBO), dan mendukung *perfect forwarding* penuh saat eksekusi invokasi.

#### Technical Requirements
1. **Move-Only Semantics:**
   - Hapus copy constructor dan copy assignment operator (`= delete`).
   - Sediakan move constructor dan move assignment operator yang berstatus `noexcept`.
2. **Type Erasure & Small Buffer Optimization (SBO):**
   - Implementasikan *type erasure* manual (menggunakan teknik storage pointer / vtable idiom internal tanpa alokasi heap jika ukuran target $\le 48$ bytes dan *alignment requirement*-nya kompatibel).
   - Jika closure atau functor melampaui kapasitas buffer SBO, alokasikan memori dinamis di heap secara aman.
3. **Perfect Forwarding Interface:**
   - Konstruktor harus berupa template yang menerima sembarang callable object `F` dengan mekanisme *forwarding reference* (`F&&`).
   - Gunakan SFINAE (`std::enable_if_t`) atau C++20 `requires clause` untuk memastikan konstruktor template tidak bertubrukan (*hide/shadow*) dengan move constructor bawaan kelas `AnyMoveTask`.
4. **Execution Protocol:**
   - Tipe signature fungsi yang diwadahi adalah `void()`.
   - Mengimplementasikan `void operator()()` yang mengeksekusi callable dan membebaskan/mereset resource secara deterministik setelah invokasi.

#### Constraints
- Wajib menggunakan C++17 atau C++20 murni.
- Tidak boleh menggunakan `std::function` internal atau pustaka pihak ketiga (misalnya `boost::type_erasure`).
- Tidak boleh terjadi memory leak dalam kondisi apa pun (wajib divalidasi dengan AddressSanitizer / Valgrind).

#### Expected Output Test Case
Tuliskan blok kode driver `main()` yang memvalidasi skenario berikut:
```cpp
// 1. Eksekusi Callable yang membungkus tipe move-only via SBO
auto ptr = std::make_unique<int>(42);
AnyMoveTask t1 = [p = std::move(ptr)]() {
    std::cout << "Value via SBO: " << *p << "\n";
};

// 2. Transfer kepemilikan task via move semantics
AnyMoveTask t2 = std::move(t1);
assert(!t1); // t1 harus berstatus empty / moved-from
assert(t2);  // t2 valid
t2();        // Output: "Value via SBO: 42"

// 3. Eksekusi Callable besar yang memaksa alokasi heap
std::array<uint8_t, 128> large_payload{};
large_payload[0] = 7;
AnyMoveTask t3 = [large_payload]() {
    std::cout << "Large functor executed: " << static_cast<int>(large_payload[0]) << "\n";
};
t3();        // Output: "Large functor executed: 7"
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi formal Value Categories ISO C++: batasan semantik antara ekspresi `lvalue`, `xvalue`, dan `prvalue`.
- [ ] Bahwa `std::move` adalah *unconditional cast* ke rvalue (`static_cast<T&&>`) dan tidak menghasilkan instruksi CPU assembly mesin saat runtime.
- [ ] Bahwa `std::forward` adalah *conditional cast* yang mempertahankan value category asli dari argumen fungsi generic template.
- [ ] Aturan kompilator terkait *Reference Collapsing*: kombinasi apa pun yang melibatkan `&` menghasilkan lvalue reference, dan hanya `&& &` yang menghasilkan rvalue reference.
- [ ] Mengapa penanda `noexcept` pada move constructor bersifat kritikal bagi algoritma kontainer STL (`std::vector`, `std::deque`) demi menjaga *Strong Exception Safety*.
- [ ] Dampak negatif `std::move` pada return statement lokal yang menggagalkan mekanisme optimasi kompilator (*Copy Elision* / NRVO).
- [ ] Aturan *"Rule of Five"* vs *"Rule of Zero"* saat merancang kelas resource manager modern.

### Saya tidak perlu menghafal:
- [ ] Detail heksadesimal kode instruksi mangling untuk template berparameter rvalue reference pada berbagai ABI kompilator (GCC Itanium ABI vs MSVC ABI).
- [ ] Algoritma internal micro-optimasi kompilator dalam melakukan pemesanan register CPU untuk ekspresi xvalue.
- [ ] Tabel pemetaan kompilator lama (C++98) yang tidak lagi relevan dengan C++ modern.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengeliminasi bug *use-after-move* serta *double-move* menggunakan compiler flags (`-Wuse-after-move`) dan Clang Static Analyzer.
- [ ] Menulis Move Constructor dan Move Assignment Operator yang bebas memory leak, aman dari kondisi *self-assignment*, dan berstatus `noexcept`.
- [ ] Mengimplementasikan *Perfect Forwarding Factory* (`make_unique`-like wrapper) menggunakan variadic templates dan `std::forward`.
- [ ] Memilih secara objektif antara strategi passing parameter: *by-value-then-move* vs *const-ref/rvalue-overloading* berdasarkan profil alokasi memori sistem.
- [ ] Merancang kelas bertipe *move-only* yang terintegrasi aman di dalam arsitektur multithreaded concurrent queue.