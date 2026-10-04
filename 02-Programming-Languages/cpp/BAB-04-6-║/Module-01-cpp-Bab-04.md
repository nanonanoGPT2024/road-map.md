# SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran**: Pemrograman Sistem C++ Modern (*Modern C++ Systems Programming*)
* **Kategori**: 02-Programming-Languages
* **Bab**: 04 — Arsitektur Berorientasi Objek Tingkat Lanjut & Polimorfisme
* **Modul**: 01 — Polimorfisme Dinamis: Tabel Virtual (*vtable*), Penunjuk Virtual (*vptr*), dan Tata Letak Memori Objek (*Object Memory Layout*)
* **Tingkat Kesulitan**: Tingkat Lanjut (*Advanced*)
* **Prasyarat**: Pemahaman mendalam tentang pointer dan referensi C++, model memori Stack vs Heap, siklus hidup objek (RAII), serta aturan *Rule of Zero/Three/Five*.
* **Standar Bahasa**: C++20 / C++23 (dengan komparasi ABI GCC/Clang Itanium dan MSVC x64)

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis** tata letak biner (*memory layout*) dari objek polimorfik, termasuk posisi *virtual pointer* (`vptr`), *padding*, dan perataan memori (*alignment*).
2. **Membedah** mekanisme kerja *Virtual Method Table* (`vtable`), resolusi pemanggilan metode pada *runtime* melalui *indirect branch*, dan implikasi kinerja *hardware* (*branch prediction* dan *instruction cache*).
3. **Mengidentifikasi** dan memitigasi bahaya *Object Slicing*, *type confusion*, serta kebocoran memori akibat *non-virtual destructors*.
4. **Mengevaluasi** perbedaan arsitektural dan biaya komputasi antara *Dynamic Polymorphism* berbasis pewarisan, *Static Polymorphism* berbasis CRTP (*Curiously Recurring Template Pattern*), dan *Type Erasure* modern (`std::variant`).
5. **Mengimplementasikan** pola arsitektur berbasis antarmuka (*pure virtual interfaces*) yang memenuhi prinsip idiom RAII, aman terhadap *exception*, serta mendukung optimasi kompilator (*devirtualization*).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma pemrograman prosedural atau pemrograman berbasis objek statis, pemanggilan fungsi bersifat deterministik pada tahap kompilasi (*compile-time dispatch*). Ketika Anda menulis `obj.compute()`, kompilator secara langsung menyematkan instruksi *call* absolut atau relatif ke alamat fungsi target di segmen `.text`.

Polimorfisme dinamis mengubah model mental ini secara radikal:

```
[Static Dispatch]  : Caller ---> Call [Alamat Fungsi Tetap]
[Dynamic Dispatch] : Caller ---> Baca vptr Objek ---> Akses Baris vtable ---> Fetch Alamat Fungsi Target ---> Call Reg/Indirect
```

Pola pikir yang harus dibangun seorang *systems engineer*:
* **Objek Polimorfik Memiliki Overhead Tersembunyi**: Objek bukan sekadar data mentah; ada metadata tersembunyi yang disuntikkan kompilator (umumnya 8 byte pointer per instans pada arsitektur 64-bit).
* **Eksekusi Tidak Lagi Monolitik**: Pemanggilan fungsi virtual melibatkan dua tingkat indireksi (*double indirection* pointer). Ini membatalkan sejumlah optimasi agresif kompilator seperti fungsi *inlining* konvensional, serta meningkatkan risiko *cache miss* pada CPU.
* **Memori Adalah Kontrak Fisik**: C++ tidak memiliki sistem *garbage collection* atau *runtime virtual machine*. Polimorfisme bekerja langsung di atas silikon melalui konvensi ABI (*Application Binary Interface*).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram 1: Tata Letak Memori Objek Polimorfik Tunggal (Itanium C++ ABI)

```
       MEMORI STACK / HEAP                     MEMORI DATA STATIS (.rodata)
  Instans Kelas Derivasi (Derived)                  Vtable untuk 'Derived'
+-----------------------------------+        +-----------------------------------+
|  Offset 0x00: vptr                |------->| Offset -0x10: Offset-to-top (0)   |
|  (Penunjuk ke Derived vtable)     |        +-----------------------------------+
+-----------------------------------+        | Offset -0x08: RTTI Pointer        |
|  Offset 0x08: Base::m_base_val    |        | (std::type_info untuk Derived)    |
+-----------------------------------+        +-----------------------------------+
|  Offset 0x0C: (Padding 4 bytes)   |        | Offset +0x00: &Derived::func1()   |
+-----------------------------------+        +-----------------------------------+
|  Offset 0x10: Derived::m_der_val  |        | Offset +0x08: &Derived::func2()   |
+-----------------------------------+        +-----------------------------------+
|  Offset 0x18: (Total Size: 24 B)  |        | Offset +0x10: &Derived::~Derived()|
+-----------------------------------+        +-----------------------------------+
```

### Diagram 2: Alur Eksekusi Resolusi Virtual Dispatch

```
[Kode Pemanggil: base_ptr->func1()]
                │
                ▼
1. Muat alamat base_ptr ke Register (misal: RAX)
                │
                ▼
2. Dereferensi RAX untuk membaca vptr (Offset 0x0): MOV RBX, [RAX]
                │
                ▼
3. Indeks vtable untuk func1 (Offset 0x0): MOV RCX, [RBX + 0x00]
                │
                ▼
4. Eksekusi Indirect Call: CALL RCX
                │
   ┌────────────┴────────────┐
   ▼                         ▼
[Cache Hit]               [Cache Miss / Branch Misprediction]
- Alamat target ada       - vtable atau instruksi target
  di L1d / BTB              belum berada di cache.
- Latensi 1-3 siklus      - Latensi 10-20+ siklus CPU stall.
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Vtable (*Virtual Method Table*)
Setiap kelas yang mendeklarasikan atau mewarisi setidaknya satu metode virtual memiliki tepat **satu** struktur `vtable` per kelas (bukan per instans). Vtable disimpan di segmen memori *read-only* (`.rodata`). Struktur vtable berisi:
* **Offset-to-top**: Nilai offset integer yang menunjukkan jarak dari sub-objek ini ke awal objek terluar (*most derived class*). Berguna dalam pewarisan ganda (*multiple inheritance*).
* **RTTI Pointer**: Pointer ke struktur data `std::type_info` yang digunakan oleh operator `typeid` dan `dynamic_cast`.
* **Array Function Pointers**: Daftar alamat memori virtual dari implementasi metode virtual aktif kelas tersebut.

### 2. Mekanisme Injeksi `vptr`
Ketika kompilator mendeteksi kata kunci `virtual`:
1. Ukuran kelas bertambah sebesar `sizeof(void*)` (8 byte pada sistem 64-bit).
2. Kompilator menyuntikkan kode tersembunyi ke awal konstruktor kelas untuk menginisialisasi `vptr` agar menunjuk ke `vtable` kelas tersebut.
3. Selama destruksi, `vptr` diatur ulang secara berurutan mundur ke `vtable` dari kelas dasar yang sedang dieksekusi destruktornya.

### 3. Pewarisan Berganda (*Multiple Inheritance*) dan Penyesuaian Pointer (*Thunks*)
Ketika sebuah kelas mewarisi lebih dari satu kelas dasar polimorfik, objek tersebut akan memiliki **beberapa** `vptr`:

```
class BaseA { virtual void a(); int x; };
class BaseB { virtual void b(); int y; };
class Derived : public BaseA, public BaseB { void a() override; void b() override; };
```

Tata letak memori `Derived`:
* `[0x00 - 0x07]` : `vptr` untuk `BaseA`
* `[0x08 - 0x0B]` : Data `BaseA::x`
* `[0x0C - 0x0F]` : Padding
* `[0x10 - 0x17]` : `vptr` untuk `BaseB`
* `[0x18 - 0x1B]` : Data `BaseB::y`

Jika sebuah pointer `BaseB*` menunjuk ke objek `Derived`, alamat pointer tersebut harus digeser maju sebesar 16 byte (`this-pointer adjustment`). Untuk mengatasi resolusi metode `b()`, kompilator menggunakan fungsi jembatan kecil yang disebut **Adjustor Thunk** untuk mengoreksi pointer `this` sebelum melompat ke fungsi utama.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Devirtualisasi (*Devirtualization*)
Devirtualisasi adalah teknik optimasi kompilator di mana pemanggilan virtual diubah kembali menjadi pemanggilan langsung (*direct call*) pada waktu kompilasi jika kompilator dapat membuktikan secara pasti tipe konkret dari objek tersebut.

Kompilator modern (GCC `-O3`, Clang `-O3`) memanfaatkan:
* **Speculative Devirtualization**: Memeriksa branch target paling sering via PGO (*Profile-Guided Optimization*), lalu membungkus panggilan virtual dalam percabangan kondisi:
  ```cpp
  if (vptr == &Vtable_For_Derived) {
      Derived::func(); // Dapat di-inline!
  } else {
      base_ptr->func(); // Indirect call fallback
  }
  ```
* **Keyword `final`**: Menandai kelas atau metode sebagai `final` memberi jaminan mutlak bagi kompilator bahwa tidak ada kelas lain yang menimpa fungsi tersebut, membuka jalan bagi devirtualisasi penuh dan *inlining*.

### Bahaya Pemanggilan Virtual dalam Konstruktor dan Destruktor
Dalam C++, polimorfisme dinamis **mati** di dalam konstruktor dan destruktor. 
* Saat konstruktor `Base` berjalan, sub-objek `Derived` belum diinisialisasi.
* `vptr` diatur untuk menunjuk ke `Base::vtable`.
* Jika fungsi virtual murni (*pure virtual function*) dipanggil secara langsung atau tidak langsung di sini, program mengalami *Undefined Behavior* dan umumnya memicu abort runtime: `pure virtual method called`.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode yang mendemonstrasikan dynamic dispatch, verifikasi ukuran memori, pembuktian keberadaan `vptr`, dan inspeksi memori secara eksplisit menggunakan C++20:

```cpp
#include <iostream>
#include <memory>
#include <cstdint>
#include <cstring>

class NonPolymorphic {
    int32_t m_id{100};
public:
    void execute() const { std::cout << "NonPoly ID: " << m_id << '\n'; }
};

class PolymorphicBase {
protected:
    int32_t m_base_id{200};
public:
    PolymorphicBase() = default;
    virtual ~PolymorphicBase() {
        std::cout << "[Destructor] PolymorphicBase destroyed\n";
    }

    virtual void process() const {
        std::cout << "[PolymorphicBase::process] ID: " << m_base_id << '\n';
    }
};

class ConcreteDerived final : public PolymorphicBase {
    int32_t m_derived_payload{999};
public:
    ConcreteDerived() = default;
    ~ConcreteDerived() override {
        std::cout << "[Destructor] ConcreteDerived destroyed\n";
    }

    void process() const override {
        std::cout << "[ConcreteDerived::process] Derived Payload: " 
                  << m_derived_payload << ", Base ID: " << m_base_id << '\n';
    }
};

int main() {
    std::cout << "--- 1. ANALISIS UKURAN MEMORI ---\n";
    std::cout << "sizeof(NonPolymorphic): " << sizeof(NonPolymorphic) << " bytes\n";
    std::cout << "sizeof(PolymorphicBase): " << sizeof(PolymorphicBase) << " bytes\n";
    std::cout << "sizeof(ConcreteDerived): " << sizeof(ConcreteDerived) << " bytes\n\n";

    std::cout << "--- 2. INSPEKSI RAW MEMORY & VPTR ---\n";
    ConcreteDerived instance;
    
    // Alamat awal objek pada arsitektur 64-bit memuat vptr
    uintptr_t* raw_memory = reinterpret_cast<uintptr_t*>(&instance);
    uintptr_t vptr_address = raw_memory[0];
    
    std::cout << "Alamat Objek Instance : 0x" << std::hex << reinterpret_cast<uintptr_t>(&instance) << '\n';
    std::cout << "Nilai vptr (ke .rodata): 0x" << std::hex << vptr_address << std::dec << '\n';

    std::cout << "\n--- 3. RESOLUSI DYNAMIC DISPATCH ---\n";
    std::unique_ptr<PolymorphicBase> poly_ptr = std::make_unique<ConcreteDerived>();
    
    // Dynamic dispatch memanggil ConcreteDerived::process()
    poly_ptr->process();

    std::cout << "\n--- 4. POLIMORFIK DESTRUKSI ---\n";
    // Unique ptr keluar dari scope, virtual destructor dipanggil
    return 0;
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 6–11 (`NonPolymorphic`)**: Kelas biasa tanpa kata kunci `virtual`. Ukurannya tepat 4 byte (`sizeof(int32_t)`). Tidak memiliki `vptr`.
* **Baris 13–24 (`PolymorphicBase`)**: 
  * Mendeklarasikan `virtual ~PolymorphicBase()`. Ini mengubah layout memori kelas.
  * Ukuran kelas menjadi 16 byte (pada arsitektur x86_64): 8 byte untuk `vptr` (offset 0), 4 byte untuk `m_base_id` (offset 8), dan 4 byte *padding* untuk mempertahankan alignment 8 byte.
* **Baris 26–37 (`ConcreteDerived final`)**:
  * Menggunakan kata kunci `final` untuk mencegah pewarisan lanjutan, memberikan petunjuk tegas kepada kompilator agar dapat menerapkan optimasi devirtualisasi.
  * Ukuran kelas menjadi 24 byte: 8 byte `vptr`, 4 byte `m_base_id`, 4 byte padding, 4 byte `m_derived_payload`, 4 byte padding akhir.
* **Baris 48–52**: Menggunakan `reinterpret_cast<uintptr_t*>` untuk membaca 8 byte pertama dari objek `instance`. Nilai `raw_memory[0]` secara fisik adalah alamat dari `vtable` untuk `ConcreteDerived` di segmen `.rodata`.
* **Baris 55–58**: Menginisialisasi `std::unique_ptr<PolymorphicBase>` dengan alamat objek `ConcreteDerived`. Pemanggilan `poly_ptr->process()` memicu resolusi runtime melalui vptr.
* **Baris 61**: Destruksi dimulai melalui pointer basis. Karena basis memiliki `virtual ~PolymorphicBase()`, kompilator membaca slot destruktor pada vtable dan memanggil `ConcreteDerived::~ConcreteDerived()` terlebih dahulu, sebelum mengeksekusi `PolymorphicBase::~PolymorphicBase()`.

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Skenario: Arsitektur Eksekusi Order Ultra-Low-Latency (Financial Engine)
Dalam mesin perdagangan frekuensi tinggi (*High-Frequency Trading / HFT*), terdapat kebutuhan untuk memproses beragam tipe instrumen: `EquityOrder`, `FuturesOrder`, dan `OptionsOrder`.

**Masalah**: 
Tim pengembang awal menggunakan polimorfisme murni (`OrderInterface*`) yang dialokasikan di atas heap melalui `std::vector<std::unique_ptr<OrderInterface>>`. Pada saat volatilitas pasar tinggi, pemrosesan 1.000.000 order per detik mengalami degradasi parah:
1. **Cache Locality Terfragmentasi**: Setiap objek dialokasikan di alamat heap terpisah (pointer chasing).
2. **Branch Misprediction Penalty**: CPU Branch Target Buffer (BTB) gagal memprediksi indirect call vtable ketika urutan order tercampur acak antara Equity, Futures, dan Option.

**Solusi Arsitektural**:
Mendesain antarmuka polimorfik yang ketat dengan:
1. Virtual interface berbasis RAII untuk lapisan ingestion fleksibel.
2. Mekanisme batch processing yang memanfaatkan devirtualisasi batch (`final` classes) dan memory arena/contiguous storage untuk mempertahankan keunggulan polimorfisme desain tanpa membayar penalti cache miss.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem pemrosesan pesan bursa saham dengan interface polimorfik, alokasi memori yang terkontrol, dan destruktor virtual yang aman:

```cpp
#include <iostream>
#include <vector>
#include <memory>
#include <string_view>
#include <chrono>

// Interface Abstraksi Murni (Pure Virtual Interface)
class IOrderProcessor {
public:
    virtual ~IOrderProcessor() = default;

    // Interface contracts
    virtual void validate() const = 0;
    virtual void route_to_exchange(std::string_view exchange_mic) = 0;
    [[nodiscard]] virtual double calculate_margin() const noexcept = 0;
};

// Implementasi Konkret 1: Ekuitas
class EquityOrderProcessor final : public IOrderProcessor {
    uint64_t m_order_id;
    double m_price;
    uint32_t m_shares;

public:
    EquityOrderProcessor(uint64_t id, double price, uint32_t shares) noexcept
        : m_order_id(id), m_price(price), m_shares(shares) {}

    ~EquityOrderProcessor() override = default;

    void validate() const override {
        if (m_shares == 0 || m_price <= 0.0) {
            throw std::invalid_argument("Equity Order: Nilai harga/lot tidak valid");
        }
    }

    void route_to_exchange(std::string_view exchange_mic) override {
        // Simulasi pengiriman data FIX protocol
        std::cout << "[EQUITY] Order " << m_order_id 
                  << " dialihkan ke bursa: " << exchange_mic << '\n';
    }

    [[nodiscard]] double calculate_margin() const noexcept override {
        return m_price * m_shares * 0.20; // 20% margin requirement
    }
};

// Implementasi Konkret 2: Derivatif Futures
class FuturesOrderProcessor final : public IOrderProcessor {
    uint64_t m_order_id;
    double m_contract_price;
    uint32_t m_contracts;
    double m_leverage;

public:
    FuturesOrderProcessor(uint64_t id, double price, uint32_t contracts, double leverage) noexcept
        : m_order_id(id), m_contract_price(price), m_contracts(contracts), m_leverage(leverage) {}

    ~FuturesOrderProcessor() override = default;

    void validate() const override {
        if (m_contracts == 0 || m_leverage < 1.0) {
            throw std::invalid_argument("Futures Order: Kontrak atau leverage tidak valid");
        }
    }

    void route_to_exchange(std::string_view exchange_mic) override {
        std::cout << "[FUTURES] Contract Order " << m_order_id 
                  << " dialihkan ke derivatif: " << exchange_mic << '\n';
    }

    [[nodiscard]] double calculate_margin() const noexcept override {
        return (m_contract_price * m_contracts) / m_leverage;
    }
};

// Engine Eksekusi Gateway
class OrderExecutionGateway {
    std::vector<std::unique_ptr<IOrderProcessor>> m_order_queue;

public:
    void register_order(std::unique_ptr<IOrderProcessor> order) {
        order->validate(); // Dynamic dispatch untuk validasi
        m_order_queue.push_back(std::move(order));
    }

    void execute_all(std::string_view target_mic) {
        std::cout << "\n=== MEMULAI EKSEKUSI BATCH TRANSAKSI ===\n";
        double total_margin = 0.0;

        for (const auto& order : m_order_queue) {
            order->route_to_exchange(target_mic); // Dynamic dispatch vtable
            total_margin += order->calculate_margin();
        }

        std::cout << "Total Margin yang Ditahan: $" << total_margin << '\n';
    }
};

int main() {
    try {
        OrderExecutionGateway gateway;

        // Memasukkan variasi objek polimorfik ke pipeline yang sama
        gateway.register_order(std::make_unique<EquityOrderProcessor>(10101, 150.25, 200));
        gateway.register_order(std::make_unique<FuturesOrderProcessor>(20202, 4500.0, 5, 10.0));
        gateway.register_order(std::make_unique<EquityOrderProcessor>(10102, 2800.50, 15));

        gateway.execute_all("XNAS"); // NASDAQ MIC
    }
    catch (const std::exception& ex) {
        std::cerr << "CRITICAL ERROR: " << ex.what() << '\n';
        return 1;
    }

    return 0;
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter | Dynamic Polymorphism (`vtable`) | Static Polymorphism (`CRTP`) | `std::variant` + `std::visit` | Raw Function Pointers (C-Style) |
| :--- | :--- | :--- | :--- | :--- |
| **Waktu Resolusi** | Runtime | Compile-time | Runtime (Closed set) | Runtime |
| **Overhead Memori** | 8 bytes per objek (`vptr`) + vtable global | 0 byte (Zero overhead) | Ukuran tipe terbesar + byte index diskriminator | 8 byte per instance per fungsi |
| **Kemampuan Inlining**| Buruk (Kecuali devirtualisasi berhasil) | Maksimal (Inlining penuh diaktifkan) | Sangat Baik (Jump table branch) | Sangat Buruk (Kompilator jarang inline pointer) |
| **Binary Footprint** | Kecil / Terpusat | Berisiko *Code Bloat* karena template instansiasi | Tergantung ukuran tipe visitor | Minimal |
| **Ekstensibilitas** | Terbuka (*Open set*: cukup warisi kelas baru) | Tertutup pada compile-time | Tertutup (*Closed set*: modifikasi varian jika tipe bertambah) | Manual, rawan type mismatch |
| **Kesesuaian Penggunaan**| Plugin dinamis, sistem GUI, API modular | Library matematika, Game Engine Core, Komputasi Intensif | State machines, AST traversal | Kompatibilitas ABI C murni |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Slicing Problem (Pemotongan Objek)
Jika objek turunan disalin ke dalam variabel bertipe kelas dasar melalui nilai (*pass-by-value*):

```cpp
ConcreteDerived derived;
PolymorphicBase base = derived; // SLICING TERJADI!
```
* **Mekanisme Kegagalan**: Variabel `base` hanya mengalokasikan ruang untuk `PolymorphicBase`. Bagian dari `ConcreteDerived` dipotong secara fisik. `vptr` dari variabel `base` diatur ke `PolymorphicBase::vtable`. Semua identitas polimorfik hilang seketika.
* **Solusi**: Selalu lewatkan objek polimorfik melalui referensi (`const Base&`) atau smart pointer (`std::unique_ptr<Base>`). Hapus copy constructor pada kelas dasar: `PolymorphicBase(const PolymorphicBase&) = delete;`.

### 2. Pure Virtual Function Called Error
Jika Anda memanggil fungsi virtual murni dari konstruktor/destruktor kelas dasar (baik langsung maupun via fungsi pembantu):

```cpp
class Base {
public:
    Base() { init(); } // BAD
    void init() { do_work(); }
    virtual void do_work() = 0;
};
```
* **Mekanisme Kegagalan**: Pada saat konstruktor `Base` dieksekusi, vtable menunjuk ke representasi `Base`. Karena `do_work()` bernilai murni (= 0), slot function pointer adalah `nullptr` atau mengarah ke handler runtime `__cxa_pure_virtual`. Program mengalami *instant crash/abort*.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Destruktor Non-Virtual pada Kelas Dasar Polimorfik
* **Kode Buruk**:
  ```cpp
  class Base { public: ~Base() {} }; // Bukan virtual!
  class Derived : public Base { int* data = new int[100]; public: ~Derived() { delete[] data; } };
  Base* p = new Derived();
  delete p; // BENCANA: Hanya ~Base() yang dipanggil! Memory leak 'data'.
  ```
* **Solusi**: Terapkan *Guideline C.35*: Destruktor kelas dasar harus `public and virtual`, atau `protected and non-virtual`.

### 2. Mengabaikan Keyword `override`
* **Kode Buruk**:
  ```cpp
  class Base { public: virtual void compute(int a) const; };
  class Derived : public Base { public: void compute(long a) const; }; // BUKAN override, tapi method baru!
  ```
* **Solusi**: Wajib gunakan `override`. Kompilator akan menolak kompilasi jika tanda tangan fungsi tidak identik secara presisi.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan C++ Core Guidelines**:
   * *C.127*: Selalu gunakan pewarisan kelas murni hanya jika antarmuka mendefinisikan kontrak tanpa implementasi detail.
   * *C.128*: Jangan gunakan `virtual`, `override`, dan `final` secara bersamaan pada fungsi yang sama. Gunakan `override` saja, atau `final` saja.
2. **Terapkan `final` pada Titik Akhir Daun Pewarisan**:
   Mendeklarasikan kelas konkret terdalam sebagai `final` membantu optimizer melakukan devirtualisasi dan penataan tata letak objek yang lebih padat.
3. **Penyembunyian Implementasi (Interface Segregation)**:
   Buat interface sesederhana mungkin (*pure abstract base class*) tanpa anggota data (*data members*). Data members pada basis menciptakan masalah perataan memori dan overhead yang tidak perlu.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Menghindari Penalti Cache Melalui Sortir Tipe (Type-Homogeneous Processing)
Meskipun menggunakan pointer polimorfik, jika Anda memiliki koleksi heterogen:
Urutkan array pointer berdasarkan alamat `vptr` sebelum perulangan intensif.

```cpp
std::sort(orders.begin(), orders.end(), [](const auto& a, const auto& b) {
    return *reinterpret_cast<void**>(a.get()) < *reinterpret_cast<void**>(b.get());
});
```
* **Alasan Teknis**: Ini mengelompokkan objek yang mengeksekusi kode yang sama ke memori lokal secara berturut-turut. Hasilnya: Branch Target Buffer (BTB) CPU tidak perlu mengganti prediksi branch secara konstan, dan instruksi tetap hangat di CPU L1-Instruction Cache.

### 2. Profiling Devirtualisasi dengan Flag Kompilator
Gunakan Clang / GCC flags untuk memeriksa apakah panggilan virtual Anda berhasil didevirtualisasi:
* GCC: `-fopt-info-vec-missed -fopt-info-inline`
* Clang: `-Rpass=openmp-opt -Rpass-missed=inline`

---

# SEKSI 16 — KEAMANAN & HARDENING

### Virtual Table Hijacking (Vtable Poisoning / Exploitation)
Ketika terjadi *buffer overflow* di atas heap pada objek polimorfik yang berdekatan, penyerang dapat menimpa nilai `vptr` objek tersebut agar menunjuk ke tabel fungsi palsu yang disiapkan di memori penyerang (*ROP gadget/shellcode*). Saat metode virtual berikutnya dipanggil, kendali eksekusi langsung beralih ke kode penyerang.

### Mitigasi:
1. **Clang Control Flow Integrity (CFI)**:
   Kompilasi dengan bendera `-fsanitize=cfi-vcall -fvisibility=hidden`. CFI menyematkan validasi bitmask sebelum pemanggilan virtual untuk memastikan `vptr` yang dituju terdaftar sah dalam ruang biner aplikasi.
2. **Hindari `reinterpret_cast` pada Objek Polimorfik**:
   Jangan gunakan cast gaya C atau `reinterpret_cast` untuk konversi polimorfik. Gunakan `dynamic_cast` (jika RTTI diaktifkan) atau pertimbangkan ulang desain menggunakan *visitor pattern* untuk menghindari *type confusion*.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Inspeksi Tata Letak Memori Menggunakan Flag Kompilator
Anda dapat meminta kompilator untuk menampilkan tata letak fisik memori dan struktur `vtable` secara presisi:
* **Clang**: `clang++ -Xclang -fdump-record-layouts -Xclang -fdump-vtable-layouts -std=c++20 main.cpp`
* **MSVC**: `cl /d1reportSingleClassLayoutConcreteDerived main.cpp`

### 2. Debugging Vtable pada GNU Debugger (GDB)
Ketika melakukan debugging proses C++:
```gdb
(gdb) set print object on
(gdb) info vtbl poly_ptr
vtable for 'ConcreteDerived' at 0x403d20:
[0]: 0x401260 <ConcreteDerived::process()>
[1]: 0x4012a0 <ConcreteDerived::~ConcreteDerived()>
[2]: 0x4012d0 <ConcreteDerived::~ConcreteDerived()>
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Ukuran Objek**: Bertambah sebesar 1 pointer (`sizeof(void*)`) jika memiliki minimal 1 fungsi virtual.
* **Letak Vptr**: Umumnya di byte 0 (offset `0x0`) dari instans objek pada arsitektur modern (Itanium ABI).
* **Vtable**: Terletak di segmen read-only `.rodata`. Dibagikan oleh semua instans dari kelas yang sama.
* **Virtual Destructor**: Wajib ada di kelas basis polimorfik untuk menghindari *Undefined Behavior* saat menghapus lewat base pointer.
* **Kata Kunci `override`**: Menjamin fungsi meng-override fungsi virtual basis secara sah pada compile-time.
* **Kata Kunci `final`**: Menghentikan pewarisan atau overriding, mengizinkan kompilator melakukan optimasi devirtualisasi (*direct call inline*).
* **Konstruktor/Destruktor**: Resolusi dinamis **mati**. Metode dieksekusi berdasarkan tipe saat itu, bukan tipe derivasi paling akhir.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1–5)

1. **Berapa ukuran `sizeof(A)` pada sistem 64-bit untuk kelas kosong berikut: `class A { virtual void f(); };`?**
   * A. 1 byte
   * B. 4 byte
   * C. 8 byte
   * D. 16 byte
   * *Jawaban*: **C**. Meskipun tidak memiliki data member, keberadaan fungsi virtual menyuntikkan satu `vptr` berukuran 8 byte.

2. **Apa yang terjadi jika Anda menghapus objek `Derived` melalui pointer `Base*`, di mana destruktor `Base` tidak ditandai sebagai `virtual`?**
   * *Jawaban*: Mengakibatkan **Undefined Behavior** (UB) menurut standar C++. Dalam praktiknya, hanya `~Base()` yang dipanggil; destruktor `~Derived()` dilewati, memicu kebocoran sumber daya.

3. **Di segmen memori mana struktur data `vtable` umumnya dialokasikan oleh kompilator?**
   * *Jawaban*: Segmen Data Read-Only (`.rodata`).

4. **Apakah `vtable` dibuat satu per instans objek atau satu per kelas?**
   * *Jawaban*: Tepat **satu per kelas**. Setiap instans objek hanya menyimpan satu pointer (`vptr`) yang menunjuk ke tabel tunggal milik kelas tersebut.

5. **Apa fungsi utama dari penandaan metode virtual dengan kata kunci `final`?**
   * *Jawaban*: Mencegah kelas turunan meng-override metode tersebut dan memberi kompilator kapabilitas untuk melakukan *devirtualisasi* (mengubah indirect call menjadi direct inlined call).

---

### Soal Intermediate (6–10)

6. **Mengapa pemanggilan fungsi virtual murni di dalam destruktor kelas dasar menghasilkan error runtime atau crash?**
   * *Jawaban*: Karena pada saat destruktor basis berjalan, bagian turunan (*derived part*) dari objek sudah dihancurkan. `vptr` telah diatur mundur ke vtable basis, di mana fungsi virtual murni tidak memiliki alamat implementasi konkret.

7. **Jelaskan apa yang dimaksud dengan istilah *Adjustor Thunk* dalam konteks pewarisan ganda (*multiple inheritance*)!**
   * *Jawaban*: Kode perantara kecil (*assembly stub*) yang disuntikkan kompilator untuk memodifikasi pointer `this` (menambah atau mengurangi offset) sebelum memanggil metode kelas dasar kedua/ketiga, guna memastikan fungsi menerima alamat awal sub-objek yang tepat.

8. **Ditinjau dari mikroarsitektur CPU, mengapa indirect branch yang terjadi pada dynamic dispatch dapat menurunkan performa aplikasi intensif komputasi?**
   * *Jawaban*: Karena alamat lompatan tidak tersimpan di instruksi itu sendiri melainkan dibaca dari register/memori. Jika pola pemanggilan berubah secara acak, *Branch Target Buffer (BTB)* CPU akan mengalami *misprediction*, memicu pengosongan instruksi pipeline (*pipeline flush*) yang membuang puluhan siklus CPU.

9. **Apa perbedaan antara *Object Slicing* dan *Type Confusion*?**
   * *Jawaban*: *Object Slicing* terjadi saat objek turunan disalin ke tipe nilai (*by-value*) basis sehingga data dan perilaku turunan terpotong secara aman (namun keliru secara logika). *Type Confusion* terjadi ketika pointer sembarang dipaksa di-cast ke tipe polimorfik yang tidak kompatibel menggunakan `reinterpret_cast`, memicu akses pointer ilegal dan celah keamanan memori.

10. **Bagaimana kompilator mengimplementasikan fitur `dynamic_cast<Derived*>(base_ptr)` di balik layar?**
    * *Jawaban*: Kompilator mengakses offset negatif dari `vptr` pada vtable untuk membaca pointer ke struktur RTTI (`std::type_info`). Algoritma internal C++ runtime (`__dynamic_cast`) kemudian menelusuri hierarki pewarisan di memori RTTI untuk memvalidasi apakah target cast valid.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Tantangan Mandiri
1. Tulis kode program yang mengekstrak langsung pointer fungsi dari `vptr` suatu objek tanpa memanggil metodenya secara langsung, kemudian panggil fungsi tersebut menggunakan function pointer casting:
   ```cpp
   using FuncPtr = void(*)(void*); // Representasi fungsi mengambil 'this'
   ```
2. Buktikan menggunakan pointer arithmetic bahwa alamat pointer bergeser pada kelas turunan yang menggunakan *Multiple Inheritance*.

---

### Proyek Praktikum Mini: "Micro-Benchmark Devirtualization Engine"

**Instruksi Proyek**:
Bangun program benchmarking sederhana yang membandingkan performa pemanggilan 100.000.000 iterasi antara:
1. Dynamic Polymorphism via `std::vector<std::unique_ptr<Base>>` (Polymorphic indirect call).
2. Direct Call dengan kelas konkret bertanda `final`.
3. Static Polymorphism menggunakan CRTP.

**Target File**: `benchmark_polymorphism.cpp`  
**Standar**: C++20  
**Instruksi Kompilasi**:
```bash
g++ -O3 -std=c++20 benchmark_polymorphism.cpp -o benchmark_bin
./benchmark_bin
```

Program harus mencetak output perbandingan waktu dalam milidetik dan ukuran memori fisik masing-masing objek menggunakan `sizeof()`. Amati perbedaan hasil ketika kompilator berhasil melakukan inline vs overhead pemanggilan vtable!