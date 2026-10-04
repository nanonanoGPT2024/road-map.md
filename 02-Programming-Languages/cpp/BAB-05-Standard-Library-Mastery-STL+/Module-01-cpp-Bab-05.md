# SEKSI 01 — IDENTITAS MODUL

* **Kategori**: 02-Programming-Languages
* **Jalur Kurikulum**: Modern C++ Software Engineering
* **Bab**: 05 — Advanced Standard Library & Ecosystem
* **Modul**: 01 — Standard Library Mastery (STL+)
* **Prasyarat**: C++ Core Syntax, RAII & Smart Pointers, Basic Templates & Concepts (C++20), Generic Programming
* **Target Tingkat Keahlian**: Advanced / Senior Systems Engineer
* **Standar Bahasa**: ISO/IEC 14882:2020 (C++20) dengan ekstensi C++23 jika relevan
* **Compiler Minimum**: GCC 11+, Clang 13+, atau MSVC 19.29+ (Visual Studio 2019 v16.10+)

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Membedah Mekanisme Internal Container**: Menganalisis layout memori, *amortized complexity*, dan *invalidation rules* dari container berurutan (*sequence*), asosiatif, dan *unordered* untuk mengeliminasi alokasi yang tidak perlu.
2. **Menguasai C++20 Ranges dan Views**: Merekayasa pipeline transformasi data berkinerja tinggi berbasis *lazy evaluation* tanpa alokasi memori tambahan (*zero dynamic allocation overhead*).
3. **Mengimplementasikan Custom Allocator & Polymorphic Memory Resources (`std::pmr`)**: Mengontrol strategi alokasi memori heap runtime dengan memigrasikannya ke arena/monotonic buffer allocator guna meminimalisasi fragmentasi dan *cache misses*.
4. **Menerapkan Vocabulary Types Modern**: Menggantikan pointer mentah dan polymorphism berbasis heap dengan `std::span`, `std::string_view`, `std::optional`, `std::variant`, dan `std::expected` (C++23) untuk meningkatkan *type-safety* dan efisiensi register CPU.
5. **Mengeksekusi Algoritma Paralel**: Mengintegrasikan *Parallel Execution Policies* (`std::execution::par_unseq`) dengan jaminan *vectorization* (SIMD) dan *thread-safety*.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model 1: STL Bukan Sekadar Library, Melainkan Ekstensi Arsitektur Mesin
Standard Template Library (STL) bukan sekadar kumpulan struktur data dan fungsi utilitas; STL adalah formalisasi abstraksi interaksi antara algoritma dan memori fisik. 
* **Container** mengelola topologi memori (kontigu vs berantai).
* **Iterator / Ranges** bertindak sebagai antarmuka abstraksi antara algoritma dan topologi memori tersebut.
* **Algoritma** dirancang murni independen dari struktur data, beroperasi pada rentang (*ranges*) linear atau semirandom traversal.
* **Allocator** memisahkan *logika data* dari *mekanika perolehan memori fisik*.

### Mental Model 2: The Cache Locality Imperative
Dalam arsitektur prosesor modern (x86_64, ARM64), memori utama (RAM) beroperasi ratusan siklus lebih lambat daripada L1 Cache (*Memory Wall*). Kompleksitas teoretis $O(1)$ pada node-based container (seperti `std::unordered_map` atau `std::list`) sering kali kalah jauh dibandingkan $O(\log N)$ atau bahkan $O(N)$ linear scan pada struktur data berbasis kontigu (`std::vector`, `std::span`, flat containers) akibat fenomena *Cache Miss* dan *Pointer Chasing*. Seorang Senior C++ Engineer memandang STL melalui lensa *Data-Oriented Design* (DOD).

```
[ CPU Core ] <---> [ L1 Cache ] <---> [ L2 Cache ] <---> [ L3 Cache ] <---> [ RAM ]
  (1 cycle)          (4 cycles)        (12 cycles)        (40 cycles)     (200+ cycles)
      ^
      |--- Cache Line (64 Bytes Loaded at once)
           Menguntungkan: std::vector, std::array, contiguous memory
           Merugikan:     std::list, std::map (Node-based pointer hopping)
```

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Komponen STL dan Aliran Data Komposisi Modern (C++20)

```
+-----------------------------------------------------------------------------------+
|                                 APPLICATION CODE                                  |
+-----------------------------------------------------------------------------------+
         |                                                 |
         v                                                 v
+------------------+                             +------------------+
| Vocabulary Types |                             |  C++20 Ranges &  |
| (span, variant,  |                             |      Views       |
|  optional, etc.) |                             | (Lazy Pipeline)  |
+------------------+                             +------------------+
         |                                                 |
         +------------------------+------------------------+
                                  |
                                  v
                    +---------------------------+
                    | Modern STL Algorithms     |
                    | (ranges::sort, transform) |
                    +---------------------------+
                                  |
         +------------------------+------------------------+
         |                                                 |
         v                                                 v
+-----------------------------+               +-----------------------------+
|     Contiguous Storage      |               |     Node-Based Storage      |
| (vector, array, deque)      |               | (list, map, unordered_map)  |
+-----------------------------+               +-----------------------------+
         |                                                 |
         +------------------------+------------------------+
                                  |
                                  v
                    +---------------------------+
                    | Memory Management Layer   |
                    | (std::allocator, std::pmr)|
                    +---------------------------+
                                  |
                                  v
                    +---------------------------+
                    | OS Virtual Memory / Heap  |
                    +---------------------------+
```

### 2. Siklus Hidup Alokasi Memori PMR vs Default Allocator

```
Standard Allocator Flow:
[Container: vector] ---> [std::allocator] ---> [operator new] ---> [OS malloc / Heap] (Costly Syscall/Lock)

PMR Flow:
[Container: pmr::vector] 
         |
         v
[std::pmr::polymorphic_allocator]
         |
         +---> [std::pmr::monotonic_buffer_resource] (Pre-allocated Stack/Heap Buffer)
         |            |
         |            +--> Sub-allocation (Pointer Bump, O(1), No locks, Zero Syscall)
         |
         +---> [Fallback: Upstream Resource] (std::pmr::new_delete_resource)
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. `std::vector<T>`: Tiga Pointer Keramat
Implementasi standar (libstdc++, libc++, MSVC STL) dari `std::vector<T>` selalu berukuran 24 bytes (pada arsitektur 64-bit), terdiri dari tiga pointer raw:
* `T* _M_start`: Menunjuk ke elemen pertama yang dialokasikan.
* `T* _M_finish`: Menunjuk ke elemen tepat setelah elemen aktif terakhir (merepresentasikan `size() = _M_finish - _M_start`).
* `T* _M_end_of_storage`: Menunjuk ke batas akhir alokasi memori yang valid (merepresentasikan `capacity() = _M_end_of_storage - _M_start`).

Faktor pertumbuhan (*growth factor*):
* GCC (`libstdc++`) dan Clang (`libc++`): $2.0 \times$
* MSVC: $1.5 \times$ (Memungkinkan memori yang telah dialokasikan sebelumnya di-*reuse* oleh allocator pada ekspansi berikutnya).

### 2. `std::unordered_map<K, V>`: Bucket Array dan Linked List
`std::unordered_map` adalah hash table tipe *separate chaining*.
* Terdiri dari array *buckets* (berisi pointer) dan sekumpulan node terhubung (*singly-linked list*).
* Setiap node memuat tuple: `std::pair<const K, V>`, nilai *cached hash code* (opsional tergantung implementasi), dan pointer `next`.
* **Kelemahan Kritis**: Setiap penyisipan elemen mengalokasikan satu *node individual* di heap. Hal ini menghancurkan *data locality*, menghasilkan fragmentasi memori, dan menyebabkan dereferensi pointer masif (*pointer chasing*) saat traversal.

### 3. C++20 Ranges: Abstraksi Tanpa Overhead
`std::ranges::views` menerapkan *lazy evaluation* melalui ekspresi templat. Komposisi menggunakan operator pipe (`|`) tidak mengeksekusi iterasi maupun mengalokasikan vector temporer; ia menghasilkan objek adaptor komposit berukuran beberapa byte yang hanya menggeser dan memfilter iterator internal saat dide-referensi (`operator*` dan `operator++`).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Iterator Invalidation Rules
Memahami kapan iterator, referensi, dan pointer menjadi *dangling* merupakan batas antara kode yang aman dan bug *Use-After-Free* (UAF) atau *Undefined Behavior* (UB).

| Container | Operasi | Dampak pada Iterator | Dampak pada Referensi/Pointer |
| :--- | :--- | :--- | :--- |
| `std::vector` | `push_back` / `insert` (jika `size > capacity`) | **Semua** tidak valid (Reallokasi) | **Semua** tidak valid |
| `std::vector` | `push_back` / `insert` (jika `size <= capacity`) | Valid s.d. titik insersi; akhir tidak valid | Valid s.d. titik insersi |
| `std::vector` | `erase` | Dari titik penghapusan hingga akhir menjadi **tidak valid** | Dari titik penghapusan hingga akhir menjadi **tidak valid** |
| `std::deque` | Insersi di awal/akhir | Semua iterator **tidak valid** | Referensi/pointer **tetap valid** |
| `std::list` | Insersi / Penghapusan | **Tetap valid** (kecuali node yang dihapus) | **Tetap valid** (kecuali node yang dihapus) |
| `std::unordered_map` | Rehash (`load_factor > max_load_factor`) | **Semua iterator tidak valid** | Referensi/pointer **tetap valid** |

### 2. Polymorphic Memory Resources (`std::pmr`)
Dimulai pada C++17, alokator tidak lagi menjadi bagian dari parameter identitas tipe kontainer yang kaku. `std::vector<int, CustomAlloc1>` dan `std::vector<int, CustomAlloc2>` adalah dua tipe yang tidak kompatibel. 

Dengan `std::pmr`, kontainer menggunakan `std::pmr::polymorphic_allocator<T>`. Polimorfisme dipindahkan ke runtime berbasis *virtual function call*, mengizinkan satu tipe kontainer menerima beragam strategi backend alokasi:
* `std::pmr::monotonic_buffer_resource`: Mengalokasikan memori dari buffer statis/stack, alokasi bersifat pointer-bump $O(1)$, tidak membebaskan memori per elemen (pembebasan dilakukan sekaligus saat *resource* di-destruct).
* `std::pmr::unsynchronized_pool_resource`: Mengelola memori dalam *pools* berbasis ukuran (*chunks*), mengeliminasi fragmentasi untuk alokasi/dealokasi berfrekuensi tinggi (tidak aman untuk multithreading tanpa sinkronisasi manual).
* `std::pmr::synchronized_pool_resource`: Varian thread-safe dari *pool resource*.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode komprehensif yang mendemonstrasikan kombinasi Modern STL: `std::span`, C++20 `ranges`, `views`, dan proyeksi algoritma.

```cpp
#include <iostream>
#include <vector>
#include <string>
#include <ranges>
#include <algorithm>
#include <span>
#include <cstdint>

struct Order {
    uint64_t id;
    std::string customer;
    double amount;
    bool is_settled;
};

// Fungsi menerima span, mengabstraksi sumber data (bisa vector, std::array, atau C-style array)
void process_large_orders(std::span<const Order> orders, double threshold) {
    // Pipeline pemrosesan menggunakan C++20 Ranges & Views
    // 1. Filter: Hanya pesanan settled dan di atas threshold
    // 2. Transform: Ekstrak nilai amount saja
    auto filtered_view = orders 
        | std::views::filter([threshold](const Order& o) { 
            return o.is_settled && o.amount >= threshold; 
          })
        | std::views::transform([](const Order& o) { 
            return o.amount; 
          });

    std::cout << "Filtered Order Amounts:\n";
    for (double amt : filtered_view) {
        std::cout << " - $" << amt << "\n";
    }

    // Demonstrasi Projection pada std::ranges::max_element
    // Menemukan pesanan tertinggi tanpa perlu lambda custom operator<
    auto highest_order_it = std::ranges::max_element(orders, {}, &Order::amount);
    
    if (highest_order_it != orders.end()) {
        std::cout << "Highest Order ID: " << highest_order_it->id 
                  << " with Amount: $" << highest_order_it->amount << "\n";
    }
}

int main() {
    const std::vector<Order> order_book = {
        {101, "Alice", 1500.50, true},
        {102, "Bob", 450.00, true},
        {103, "Charlie", 3200.00, false}, // Tidak settled
        {104, "David", 8900.75, true},
        {105, "Eve", 120.00, true}
    };

    // Melewatkan std::vector ke std::span secara implisit tanpa alokasi
    process_large_orders(order_book, 1000.0);

    return 0;
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 9–14**: Definisi struct `Order`. Perhatikan layout byte-nya; compiler akan menyisipkan padding setelah `bool is_settled` untuk alignment 8-byte.
* **Baris 17**: `void process_large_orders(std::span<const Order> orders, double threshold)`. Penggunaan `std::span<const Order>` menghindari penyalinan (*zero-copy*) dan tidak mengikat fungsi ke tipe penampung spesifik (`std::vector`). Objek `std::span` hanya membawa satu pointer dan satu ukuran integer (`sizeof(span) == 16 bytes` pada 64-bit).
* **Baris 21–27**: Pipeline C++20 Ranges.
  * Operator pipe `|` mengomposisikan objek *range adapter*.
  * `std::views::filter` membungkus view sebelumnya dan menyaring elemen on-the-fly. Evaluasi adalah *lazy*—predikat filter hanya dieksekusi saat loop iterator berjalan.
  * `std::views::transform` mengonversi setiap `Order` yang lolos menjadi tipe `double`. Seluruh proses ini berjalan tanpa heap allocation sama sekali.
* **Baris 29–32**: Iterasi mengeksekusi pipeline di atas secara inline. Compiler dapat mengoptimalkan loop ini, sering kali melakukan *loop unrolling* atau *vectorization* sebanding dengan loop manual C.
* **Baris 36**: `std::ranges::max_element(orders, {}, &Order::amount);`. Menggunakan *algorithm projection* (fitur C++20). Parameter kedua adalah predikat pembanding default (`std::less{}`), dan parameter ketiga adalah *pointer-to-member* `&Order::amount` yang bertindak sebagai pemilih proyeksi secara langsung tanpa overhead lambda closure manual.

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Sistem Pemrosesan Log Jaringan Berkecepatan Tinggi (High-Frequency Trading Network Ingress)
**Skenario**: Sebuah sistem audit jaringan menerima ratusan ribu frame data log biner per detik. Setiap pesan harus diparsing, divalidasi, dan dimasukkan ke dalam antrean pemrosesan lokal sebelum dibersihkan.
**Masalah**: Penggunaan alokator standar (`std::allocator`) dengan `std::vector` atau `std::string` memicu *contention* pada heap OS (`malloc`/`free`), menyebabkan latensi tail (99th percentile) melonjak hingga mili-detik akibat pemanggilan lock internal pada heap allocator runtime.
**Solusi**: Menerapkan arsitektur zero-allocation pemrosesan berbasis `std::pmr::monotonic_buffer_resource` yang didukung oleh memory buffer statis pada stack untuk menangani alokasi rentang hidup singkat, dikombinasikan dengan `std::string_view` dan `std::variant` untuk merepresentasikan payload secara *type-safe* tanpa pointer dinamis.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem pemrosesan log yang memanfaatkan `std::pmr`, `std::variant`, dan `std::string_view` untuk menjamin zero heap allocations pada hot-path.

```cpp
#include <iostream>
#include <memory_resource>
#include <vector>
#include <string_view>
#include <variant>
#include <array>
#include <cstdint>
#include <chrono>

// Definisi berbagai tipe payload
struct Heartbeat { uint64_t timestamp; };
struct TradeExecution { uint64_t trade_id; double price; uint32_t volume; };
struct SystemAlert { int32_t severity; std::string_view message; };

// Variant memori lokal tanpa alokasi heap
using IngressPayload = std::variant<Heartbeat, TradeExecution, SystemAlert>;

struct IngressPacket {
    uint32_t sequence_id;
    IngressPayload payload;
};

// Visitor pattern untuk memproses variant
struct PacketDispatcher {
    void operator()(const Heartbeat& hb) const {
        // Hot-path processing Heartbeat
        (void)hb;
    }
    void operator()(const TradeExecution& tx) const {
        // Hot-path processing Trade
        (void)tx;
    }
    void operator()(const SystemAlert& sa) const {
        std::cout << "[ALERT] Level " << sa.severity << ": " << sa.message << "\n";
    }
};

void run_hot_path_network_ingress() {
    // 1. Siapkan Buffer Memori di Stack sebesar 64 KB
    std::array<std::byte, 65536> stack_buffer;

    // 2. Bungkus ke dalam Monotonic Buffer Resource
    // Jika stack_buffer habis, ia fallback ke null_memory_resource (melempar std::bad_alloc)
    // untuk menjamin TIDAK ADA alokasi heap tersembunyi.
    std::pmr::monotonic_buffer_resource mem_pool(
        stack_buffer.data(), 
        stack_buffer.size(), 
        std::pmr::null_memory_resource()
    );

    // 3. Buat PMR Container yang menggunakan memory resource lokal di atas
    std::pmr::vector<IngressPacket> packet_queue(&mem_pool);
    packet_queue.reserve(1000); // Alokasi instan berbasis pointer-bump dari stack_buffer

    // 4. Simulasi Ingestion Loop
    for (uint32_t i = 0; i < 5; ++i) {
        if (i % 2 == 0) {
            packet_queue.push_back(IngressPacket{
                i, TradeExecution{1000000ULL + i, 4523.50 + i, 100}
            });
        } else {
            packet_queue.push_back(IngressPacket{
                i, SystemAlert{2, "Warning: Latency jitter detected"}
            });
        }
    }

    // 5. Konsumsi antrean menggunakan std::visit (Pattern Matching)
    PacketDispatcher dispatcher;
    for (const auto& packet : packet_queue) {
        std::visit(dispatcher, packet.payload);
    }

    std::cout << "Processed " << packet_queue.size() << " packets entirely on stack memory.\n";
    // Seluruh memori packet_queue dibersihkan instan saat stack unwinds (No OS system call overhead)
}

int main() {
    run_hot_path_network_ingress();
    return 0;
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Node-Based vs Contiguous Containers vs Modern Flat Alternatives

| Kriteria | `std::vector` | `std::list` | `std::unordered_map` | `std::flat_map` (C++23) |
| :--- | :--- | :--- | :--- | :--- |
| **Penyimpanan Memori** | Kontigu | Terfragmentasi (Node) | Bucket Array + Nodes | Dua `std::vector` (K/V terpisah) |
| **Cache Locality** | Maksimum (L1/L2 Friendly) | Buruk (Pointer chasing) | Buruk | Sangat Tinggi |
| **Lookup Latency** | $O(N)$ scanning | $O(N)$ pointer walk | $O(1)$ amortized, terburuk $O(N)$ | $O(\log N)$ binary search |
| **Insersi Tengah** | $O(N)$ memmove | $O(1)$ pointer rewrite | $O(1)$ amortized | $O(N)$ memmove |
| **Memory Overhead** | Hampir 0 (hanya capacity buffer) | 2 Pointer per elemen (16B) | 1-2 Pointer + Hash Code per node | Rendah (tidak ada node overhead) |
| **Ukuran Elemen Ideal** | Sembarang, ideal untuk POD/Kecil | Struktur masif, non-movable | Objek yang mahal di-copy/move | Tipe kecil s.d. menengah |

### Analisis Kritis: Kapan Memilih PMR Monotonic Buffer?
* **Kelebihan**: Alokasi memori berbiaya beberapa instruksi CPU (hanya increment pointer). Sangat cepat, *thread-local*, deterministik, bebas fragmentasi heap.
* **Kekurangan**: Tidak dapat merebut kembali (*reclaim*) memori elemen individual. Pemanggilan `vector::clear()` atau `vector::erase()` menghancurkan objek (`T::~T()`), namun memori fisiknya tidak berkurang hingga seluruh arena dimusnahkan.

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. `std::string_view` Dangling Reference
`std::string_view` tidak memiliki (*non-owning*) karakter yang ditunjuknya.
```cpp
// SANGAT BERBAHAYA: Mengembalikan string_view ke objek temporer
std::string_view get_sub_string() {
    std::string s = "Temporary Data that is long enough to bypass SSO";
    return std::string_view(s).substr(0, 5); // CRITICAL BUG: 's' mati di akhir scope fungsi!
}
// Hasilnya: Undefined Behavior saat diakses oleh pemanggil.
```

### 2. Ranges Infinite Evaluation
Hati-hati saat menggunakan views generator tak terbatas seperti `std::views::iota`:
```cpp
auto infinite = std::views::iota(0);
// Jangan pernah memasukkan infinite view ke algoritma tanpa batas
// auto max_val = std::ranges::max(infinite); // DEADLOCK / INFINITE LOOP!
// Solusi: Selalu batasi dengan views::take
auto bounded = infinite | std::views::take(100);
```

### 3. Move Semantics pada `std::variant`
Jika operasi copy/move assignment pada elemen yang disimpan melempar eksepsi, variant dapat masuk ke status tidak valid yang disebut **`valueless_by_exception`**. Selalu cek `.valueless_by_exception()` sebelum mengakses jika tipe internal Anda melempar eksepsi saat relokasi.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mengabaikan Alokasi Ulang pada `std::vector` (Reallocation Churn)
*Salah*:
```cpp
std::vector<int> data;
for(int i = 0; i < 1000000; ++i) {
    data.push_back(i); // Memicu reallokasi berulang kali (~20 kali heap malloc + memcpy)
}
```
*Benar*:
```cpp
std::vector<int> data;
data.reserve(1000000); // 1 Alokasi tunggal di muka
for(int i = 0; i < 1000000; ++i) {
    data.push_back(i);
}
```

### Kesalahan 2: Menggunakan `std::find` alih-alih Member Function pada Set/Map
*Salah*:
```cpp
std::set<int> my_set = { /* jutaan data */ };
auto it = std::find(my_set.begin(), my_set.end(), 42); // Linear search O(N), merusak pohon RB!
```
*Benar*:
```cpp
auto it = my_set.find(42); // Logarithmic search O(log N) menggunakan struktur internal BST
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Default-lah ke `std::vector`**: Kecuali ada bukti profil performa bahwa linked list atau hash map lebih unggul untuk pola akses data spesifik Anda, selalu gunakan `std::vector` secara default.
2. **Prioritaskan `std::span<T>` dan `std::string_view` untuk Interface**: Parameter fungsi *read-only* sebaiknya menerima `std::span<const T>` atau `std::string_view` daripada `const std::vector<T>&` atau `const std::string&`. Ini memberikan fleksibilitas tanpa beban alokasi.
3. **Konvensi Transparent Comparison pada Map (`std::less<>`)**:
   Gunakan pembanding heterogen agar pencarian di `std::map<std::string, T>` dapat menerima `std::string_view` tanpa memicu pembuatan `std::string` temporer:
   ```cpp
   std::map<std::string, int, std::less<>> lookup_table; // Mendukung transparent lookup
   std::string_view key = "fast_lookup";
   auto it = lookup_table.find(key); // Tidak ada alokasi heap sementara
   ```
4. **Hindari `std::bind`**: Selalu gunakan generic lambdas C++20 (`[](auto&& arg) { ... }`) alih-alih `std::bind`. Lambdas dioptimalkan langsung oleh compiler dan jauh lebih mudah di-*inline*.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Small String Optimization (SSO) & Small Buffer Optimization (SBO)
Implementasi standar C++ modern tidak mengalokasikan memori heap untuk string pendek (biasanya $\le 15$ bytes pada libc++/libstdc++, atau $\le 22$ bytes pada MSVC). Kapasitas buffer langsung berada di dalam memori internal objek `std::string` itu sendiri via union.

```
Layout std::string (Typical 64-bit SSO):
+----------------------------------------------------+
|  ptr/buffer (16-24 bytes)      | size_t | capacity |
+----------------------------------------------------+
  ^
  |--- Jika size <= 15 bytes: Karakter disimpan langsung di sini.
  |--- Jika size >  15 bytes: Disimpan di Heap, field ini jadi pointer T*.
```

### Algoritma Paralel & SIMD Vectorization
Gunakan *Execution Policies* dari header `<execution>` untuk operasi skala masif:
```cpp
#include <vector>
#include <algorithm>
#include <execution>

void parallel_vector_compute(std::vector<float>& data) {
    // Mengeksekusi secara multithreading (par) DAN SIMD vectorized (unseq)
    // Syarat: Mutex/lock TIDAK BOLEH digunakan di dalam lambda (dapat memicu deadlock SIMD)
    std::sort(std::execution::par_unseq, data.begin(), data.end());
}
```

---

# SEKSI 16 — KEAMANAN & HARDENING

1. **Atasi Out-of-Bounds Subscripting**:
   `operator[]` pada `std::vector` dan `std::span` tidak melakukan bounds-checking pada rilis optimasi produksi demi kecepatan.
   * Gunakan `vector::at(index)` jika sumber indeks berasal dari data input eksternal yang tidak tepercaya (melempar `std::out_of_range`).
   * Aktifkan *Hardened Libstdc++ / MSVC Iterator Debugging* pada pipeline CI/CD:
     * GCC: `-D_GLIBCXX_ASSERTIONS`
     * Clang: `-D_LIBCPP_ENABLE_HARDENED_MODE=1`
2. **Karantina Denial of Service (DoS) pada `std::unordered_map`**:
   `std::hash` standar untuk tipe integral adalah fungsi identitas atau hash sederhana yang rentan terhadap serangan manipulasi collision (*Hash Collision Attack*). Jika data kunci dikontrol oleh user eksternal, gantikan dengan hash anti-kolisi yang kuat secara kriptografis atau gunakan *SipHash* / *MurmurHash* sebagai custom hasher.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Pelacakan Custom PMR Memory Resource
Untuk mendeteksi kebocoran dan memantau pemakaian alokasi pada hot-path, bangun *Decorator Memory Resource*:

```cpp
#include <memory_resource>
#include <iostream>

class TrackingMemoryResource : public std::pmr::memory_resource {
public:
    explicit TrackingMemoryResource(std::pmr::memory_resource* upstream)
        : upstream_resource_(upstream) {}

    size_t total_allocated() const { return allocated_bytes_; }

protected:
    void* do_allocate(size_t bytes, size_t alignment) override {
        allocated_bytes_ += bytes;
        std::cout << "[ALLOC] " << bytes << " bytes, align " << alignment << "\n";
        return upstream_resource_->allocate(bytes, alignment);
    }

    void do_deallocate(void* p, size_t bytes, size_t alignment) override {
        allocated_bytes_ -= bytes;
        std::cout << "[DEALLOC] " << bytes << " bytes\n";
        upstream_resource_->deallocate(p, bytes, alignment);
    }

    bool do_is_equal(const std::pmr::memory_resource& other) const noexcept override {
        return this == &other;
    }

private:
    std::pmr::memory_resource* upstream_resource_;
    size_t allocated_bytes_ = 0;
};
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

* **`std::vector<T>`**: Tiga pointer (start, finish, storage end). Reserve di awal untuk mengeliminasi reallokasi berulang.
* **`std::span<T>`**: Pointer + Size, non-owning view ke buffer kontigu. Menggantikan pointer C dan pointer-length pairs.
* **`std::string_view`**: Non-owning view ke string. Waspadai *lifetime dangling*.
* **`std::variant<Ts...>`**: Type-safe replacement untuk C-union. Ukuran sebanding dengan data terbesar + discriminator tag byte.
* **`std::pmr`**: Memindahkan strategi alokasi ke runtime buffer/arena, mengeliminasi overhead sistem alokasi heap standar.
* **`std::ranges::views`**: Lazy, composable, evaluasi on-the-fly, *zero dynamic memory footprint*.
* **Parallel Execution Policies**:
  * `std::execution::seq` (Single-threaded serial)
  * `std::execution::par` (Multithreaded parallelism)
  * `std::execution::par_unseq` (Multithreaded + SIMD Vectorization)

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Bagian 1: Basic (Pilihan Ganda)

1. **Berapa ukuran default dari `std::vector<int>` kosong pada arsitektur 64-bit?**
   * A. 8 bytes
   * B. 16 bytes
   * C. 24 bytes
   * D. 32 bytes

2. **Manakah container berikut yang menjamin data tersimpan secara kontigu (*contiguous*) dalam memori fisik?**
   * A. `std::list`
   * B. `std::deque`
   * C. `std::vector`
   * D. `std::set`

3. **Operasi mana yang memicu iterator invalidation secara global untuk SEMUA elemen pada `std::vector`?**
   * A. `pop_back()`
   * B. `push_back()` ketika `size() == capacity()`
   * C. `push_back()` ketika `size() < capacity()`
   * D. Mengakses elemen menggunakan `operator[]`

4. **Apa karakteristik utama dari `std::views` pada C++20?**
   * A. Menyalin seluruh data ke kontainer temporer
   * B. Melakukan komputasi secara *lazy* (hanya saat elemen diakses)
   * C. Membutuhkan sinkronisasi mutex di background
   * D. Hanya dapat digunakan dengan `std::string`

5. **Apa fungsi utama dari Small String Optimization (SSO)?**
   * A. Mengompres string menggunakan algoritma Huffman
   * B. Mencegah alokasi heap untuk string yang berukuran pendek
   * C. Mengubah string menjadi bilangan integer secara otomatis
   * D. Mengunci string dalam L1 cache

---

### Bagian 2: Intermediate (Analisis Kasus & Troubleshooting)

6. **Analisis potongan kode berikut. Apakah bug fatal yang terkandung di dalamnya?**
   ```cpp
   std::vector<int> v = {1, 2, 3, 4, 5};
   for(auto it = v.begin(); it != v.end(); ++it) {
       if(*it == 3) {
           v.erase(it);
       }
   }
   ```
   * A. Kebocoran memori (Memory leak)
   * B. Infinite loop
   * C. Undefined behavior karena iterator `it` menjadi tidak valid setelah `.erase(it)`
   * D. Gagal kompilasi karena `erase` tidak menerima iterator

7. **Apa perbedaan mendasar antara `std::pmr::monotonic_buffer_resource` dan alokator standar `std::allocator`?**
   * A. Monotonic buffer membebaskan memori per objek saat destructors dipanggil
   * B. Monotonic buffer hanya memajukan pointer (pointer bump) dan tidak membebaskan memori individual hingga seluruh resource dihancurkan
   * C. Monotonic buffer lebih lambat karena thread-safe
   * D. Monotonic buffer tidak bisa digunakan bersama `std::pmr::vector`

8. **Kapan `std::variant::valueless_by_exception()` menghasilkan nilai `true`?**
   * A. Ketika diinisialisasi tanpa nilai default
   * B. Ketika destruktor salah satu tipe di dalamnya gagal dieksekusi
   * C. Ketika proses transisi tipe melempar eksepsi di tengah assignment/konstruksi
   * D. Ketika variant menyimpan pointer `nullptr`

9. **Mengapa `std::views::filter` tidak dapat dimodelkan sebagai `random_access_range` meskipun kontainer asalnya adalah `std::vector`?**
   * A. Karena filter memerlukan mutasi data
   * B. Karena operasi indexing $O(1)$ tidak mungkin dilakukan tanpa memindai predikat dari elemen-elemen sebelumnya
   * C. Karena filter mengalokasikan array baru
   * D. Karena C++20 melarang random access pada view

10. **Apa risiko keamanan utama dari penggunaan `std::string_view` sebagai return type fungsi?**
    * A. Stack overflow
    * B. Dangling pointer dereference jika string_view merujuk pada buffer temporer/lokal
    * C. Memory leak
    * D. Deadlock pada multithreading

---

### Kunci Jawaban Kuis

1. **C** — `std::vector` terdiri dari tiga pointer raw (start, finish, end of storage), berukuran $3 \times 8 = 24$ bytes.
2. **C** — `std::vector` menjamin memori kontigu. `std::deque` adalah array of chunks (non-contiguous global).
3. **B** — Jika alokasi penuh, reallokasi heap memindahkan data ke area baru; seluruh pointer dan iterator lama invalid.
4. **B** — Views mengevaluasi transformasi secara *lazy* tanpa menyalin data.
5. **B** — SSO menyimpan string pendek langsung pada internal buffer tanpa `malloc`.
6. **C** — `erase()` menginvalir iterator pada dan setelah titik insersi/penghapusan. `it` yang di-increment setelah erase akan memicu UB. Solusi: `it = v.erase(it);` atau `std::erase(v, 3);`.
7. **B** — Monotonic buffer menggunakan alokasi pointer-bump dan mendelegasikan pembebasan massal di akhir lifetime arena.
8. **C** — Sesuai standar, jika konstruktor tipe pengganti melempar eksepsi saat relokasi, variant masuk status *valueless*.
9. **B** — Algoritma tidak tahu berapa elemen yang tersaring sebelum indeks $K$ tanpa menghitungnya secara sekuensial ($O(K)$).
10. **B** — Non-owning semantics; jika underlying string dihancurkan saat fungsi return, `string_view` menunjuk ke memori bebas (*dangling*).

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: High-Performance In-Memory Time-Series Metric Aggregator

Bangun sebuah modul aggregator metrik CPU/Memory telemetri menggunakan konsep Modern STL yang telah dipelajari dengan batasan ketat:

#### Kebutuhan Fungsional & Spesifikasi:
1. **Data Model**:
   * Definisikan struct `MetricRecord` yang berisi `uint64_t timestamp`, `uint32_t metric_id`, dan `double value`.
2. **Memory Constraint (Zero-Heap Hot-Path)**:
   * Gunakan `std::pmr::monotonic_buffer_resource` yang di-backed oleh `std::array<std::byte, 1024 * 1024>` (1 Megabyte buffer di stack atau static memory).
   * Gunakan `std::pmr::vector<MetricRecord>` untuk mengumpulkan metrik.
3. **Analytics Engine (C++20 Ranges & Algorithms)**:
   * Implementasikan fungsi analisis yang menerima `std::span<const MetricRecord>`.
   * Buat pipeline yang memfilter metrik berdasarkan `metric_id` tertentu, mengabaikan data invalid (`value < 0.0`), dan memproyeksikan nilai metrik tersebut.
   * Gunakan algoritma paralel `std::sort` dengan policy `std::execution::par` untuk mengurutkan record secara kronologis.
   * Hitung nilai rata-rata (*mean*) dan nilai maksimum menggunakan `std::accumulate` / `std::reduce` dan `std::ranges::max_element`.
4. **Validasi & Observabilitas**:
   * Cetak alamat memori data pertama dan terakhir untuk memverifikasi bahwa seluruh buffer berada di dalam blok memori `std::array` statis/stack (bukan dialokasikan oleh heap kernel).
   * Uji batas kapasitas: Tangani `std::bad_alloc` ketika monotonic resource mencapai kapasitas maksimalnya secara elegan.