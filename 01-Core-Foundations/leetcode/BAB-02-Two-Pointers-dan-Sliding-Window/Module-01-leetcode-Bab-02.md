# Bab 02: Dynamic Arrays & Contiguous Memory Mechanics
## Modul 01: Memory Layout, Cache Locality, dan Analisis Amortisasi Array Dinamis

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
* Membedakan model alokasi memori antara array statis berbasis stack dan array dinamis berbasis heap pada level representasi pointer, cache line, dan padding memori.
* Menghitung dan membuktikan kompleksitas waktu amortisasi operasi penambahan elemen (*amortized time complexity*) menggunakan *Accounting Method* dan *Potential Method*.
* Mengidentifikasi degradasi performa akibat *cache miss* (L1/L2/L3) pada traversal array multidimensi (*Row-major* vs *Column-major*) dan dynamic array resizes.
* Mengimplementasikan struktur data Dynamic Array kustom thread-safe minimal dalam C++ atau Go yang mengoptimalkan faktor ekspansi (*geometric growth factor*) untuk meminimalkan fragmentasi memori dan translasi virtual memory via page faults.

---

### 2. Prerequisite
* Pemahaman fundamental mengenai Notasi Big-O (Bab 01: Analisis Asimptotik, *Worst-case*, *Average-case*, dan *Best-case*).
* Konsep pointer dasar, referensi memori, manipulasi memori mentah (`malloc`, `free`, `new`, `delete`), serta segmentasi memori OS (Stack, Heap, Data/BSS).
* Arsitektur CPU dasar: register memori, arsitektur Von Neumann, dan hierarki cache L1/L2/L3.

---

### 3. Concept
Array adalah blok memori kontinu (*contiguous memory block*) yang menyimpan elemen-elemen dengan tipe data homogen berukuran tetap ($S$ bytes). Karena sifatnya yang berurutan secara fisik dalam memori virtual, elemen ke-$i$ dari array yang dimulai pada alamat dasar $B$ (*base address*) dapat diakses secara langsung melalui formula kalkulasi pointer berorde waktu $O(1)$:

$$\text{Address}(A[i]) = B + (i \times S)$$

Dynamic Array (seperti `std::vector` pada C++, `ArrayList` pada Java, `slices` pada Go, atau `list` pada Python) membungkus array statis dengan lapisan abstraksi dinamis. Dynamic Array mengelola tiga metadata krusial:
1. **Pointer (`data`)**: Menunjuk ke awal blok memori yang dialokasikan di heap.
2. **Size / Length (`size`)**: Jumlah elemen yang saat ini aktif digunakan dalam struktur.
3. **Capacity (`capacity`)**: Alokasi total ruang memori fisik yang dialokasikan sebelum array harus melakukan realokasi (*resizing*).

Ketika operasi penambahan elemen (`push_back` / `append`) dilakukan saat $\text{size} = \text{capacity}$, sistem alokator memori harus:
1. Meminta blok memori baru berukuran $\text{capacity} \times \alpha$ (di mana $\alpha$ adalah *growth factor*, biasanya $1.5$ atau $2.0$).
2. Menyalin (*copy*) atau memindahkan (*move semantics*) semua elemen lama dari buffer lama ke buffer baru.
3. Mendealokasikan buffer lama untuk mencegah kebocoran memori (*memory leak*).
4. Memperbarui pointer internal ke buffer baru dan menyisipkan elemen baru.

Meskipun proses realokasi membutuhkan waktu $O(N)$ untuk menyalin $N$ elemen, frekuensi realokasi menurun secara eksponensial seiring bertambahnya ukuran array, menghasilkan biaya rata-rata per operasi sebesar $O(1)$ amortisasi.

---

### 4. Why
1. **Cache Locality dan Memory Wall**: Kecepatan CPU modern jauh melampaui latensi akses Dynamic RAM (DRAM), menciptakan fenomena *Memory Wall*. Array memanfaatkan *Spatial Locality*: saat satu elemen dimuat ke register, seluruh *cache line* (umumnya 64 byte pada arsitektur x86_64 dan ARM64) ikut ditarik ke L1 cache. Struktur non-kontigu (seperti Linked List) gagal memanfaatkan L1 cache line, menyebabkan latensi stall CPU hingga 200x lebih lambat per traversal dereference pointer.
2. **Amortisasi Beban Alokator OS**: Pemanggilan *system call* alokasi memori kernel (seperti `brk` atau `mmap` di POSIX) memiliki overhead siklus CPU yang signifikan. Dynamic array meminimalkan pemanggilan alokator dengan menerapkan strategi *geometric resizing*, menghindari *syscall per push*.
3. **Pondasi Algoritma Kompetitif & Produksi**: Solusi LeetCode tingkat lanjut (seperti Sliding Window, Two Pointers, In-place Partitioning, Dynamic Programming State Caching) mengasumsikan traversal $O(1)$ berbiaya instruksi rendah yang hanya dapat dijamin oleh array kontigu.

---

### 5. What
Komponen inti penyusun dynamic array di tingkat rekayasa memori:

* **Growth Factor ($\alpha$)**: Faktor pengali kapasitas. Nilai umum:
  * $\alpha = 2.0$ (Implementasi awal GCC libstdc++, Go runtime slices).
  * $\alpha = 1.5$ (MSVC STL, Facebook Folly `fbvector`). Nilai $\alpha < 1.618$ (Rasio Emas / Golden Ratio) memungkinkan memori yang didealokasikan sebelumnya dapat digabungkan kembali (*coalesced*) dan dialokasikan untuk realokasi masa depan, menghindari *virtual memory fragmentation*.
* **Memory Alignment**: Penempatan data pada alamat memori yang merupakan kelipatan dari ukuran tipe data (misal: integer 4-byte harus berada di alamat yang habis dibagi 4) untuk mencegah *unaligned memory access penalty*.
* **Trivially Copyable vs Non-Trivially Copyable**: Jika tipe data elemen bertipe primitif atau *trivially copyable*, realokasi memori dapat dioptimalkan secara drastis menggunakan instruksi vektorisasi hardware (`memcpy` / AVX-512) tanpa memanggil konstruktor/destruktor satu per satu.

---

### 6. How
Alur eksekusi internal saat memanggil `push_back(val)`:

```
[Mulai push_back(val)]
        |
        v
apakah size < capacity?
   /         \
 (Ya)        (Tidak)
  |             |
  |             v
  |      [Kalkulasi New Capacity: capacity * growth_factor]
  |             |
  |             v
  |      [Panggil Allocator Memori Heap Baru]
  |             |
  |             v
  |      [Pindahkan/Salin elemen lama ke buffer baru]
  |             |
  |             v
  |      [Deallokasi buffer lama]
  |             |
  |             v
  |      [Update Pointer base address ke buffer baru]
  |             |
  +<------------+
  |
  v
[Tulis 'val' ke address: base + (size * sizeof(T))]
  |
  v
[size = size + 1]
  |
  v
[Selesai]
```

#### Pembuktian Amortisasi (Potential Method)
Fungsi potensial $\Phi$ didefinisikan sebagai:
$$\Phi(D_i) = 2 \cdot \text{size}_i - \text{capacity}_i$$
* Sesaat setelah ekspansi (misal $\alpha = 2$), $\text{capacity} = 2 \cdot \text{size}$, sehingga $\Phi = 0$.
* Tepat sebelum ekspansi, $\text{size} = \text{capacity}$, sehingga $\Phi = \text{size}$.
* Biaya amortisasi $\hat{c}_i = c_i + \Phi(D_i) - \Phi(D_{i-1})$:
  * Kasus tanpa ekspansi: $c_i = 1$, $\Delta \Phi = (2(\text{size}+1) - \text{capacity}) - (2\text{size} - \text{capacity}) = 2$.
    $$\hat{c}_i = 1 + 2 = 3 = O(1)$$
  * Kasus dengan ekspansi dari $N$ ke $2N$: $c_i = N + 1$, $\Delta \Phi = (2(N+1) - 2N) - (2N - N) = 2 - N$.
    $$\hat{c}_i = (N + 1) + (2 - N) = 3 = O(1)$$
Terbukti secara matematis bahwa biaya amortisasi dari setiap operasi penambahan adalah konstan $O(1)$.

---

### 7. Analogy
Bayangkan Anda menyewa loker penyimpanan arsip fisik. 
* Pada awalnya, Anda menyewa unit loker dengan 2 slot laci. 
* Saat kedua slot laci terisi dan Anda membawa map ketiga, perusahaan loker tidak bisa menambah laci baru di dinding yang sama karena keterbatasan struktur beton gedung.
* Anda dipaksa menyewa unit loker baru di ruangan lain yang memiliki 4 slot laci kosong. Anda harus mengangkut map dari loker lama ke loker baru, lalu mengembalikan kunci loker lama. 
* Proses pindah fisik ini memakan waktu seharian ($O(N)$), tetapi Anda kini memiliki ruang sisa. Untuk berkas berikutnya, Anda hanya butuh 1 detik ($O(1)$) untuk menyelipkannya ke laci kosong yang tersedia.

---

### 8. Diagram

#### A. Kontiguitas Heap dan Struktur Internal
```
+-------------------------------------------------------------+
| STACK (Metadata Object)                                     |
|  [ data* ]  ---> Menunjuk ke Base Address di Heap (0x1000)  |
|  [ size  ]  ---> 3                                          |
|  [ cap   ]  ---> 4                                          |
+-------------------------------------------------------------+
        |
        v
+-------------------------------------------------------------+
| HEAP (Contiguous Buffer)                                    |
| Base: 0x1000                                                |
| +-----------------+-----------------+-----------------+-----+
| | Index 0         | Index 1         | Index 2         | Unused
| | Val: 42         | Val: 88         | Val: 19         | Free |
| | Addr: 0x1000    | Addr: 0x1004    | Addr: 0x1008    | 0x100C
| +-----------------+-----------------+-----------------+-----+
+-------------------------------------------------------------+
```

#### B. Cache Line Fetch (64 Bytes)
```
CPU Memory Request -> Alamat 0x1000
L3 Cache / RAM: Mengembalikan 1 Cache Line (64-byte block):
[ 0x1000 - 0x103F ] dimuat sekaligus ke L1 Data Cache.
Jika tipe data int32_t (4 byte), elemen index 0 hingga 15 
seketika tersedia di cache L1 berkecepatan ~1ns.
```

---

### 9. Simple Example
Perbandingan alokasi statis versus dinamis dalam C++ standar:

```cpp
#include <iostream>
#include <vector>

int main() {
    // 1. Array statis (Stack allocation, ukuran immutable terikat compile-time)
    int static_arr[4] = {10, 20, 30, 40};
    
    // 2. Dynamic Array (Metadata di stack, buffer buffer di heap)
    std::vector<int> dynamic_arr;
    dynamic_arr.reserve(2); // Pre-alokasi kapasitas awal = 2

    std::cout << "Cap: " << dynamic_arr.capacity() << ", Size: " << dynamic_arr.size() << "\n";
    dynamic_arr.push_back(100);
    dynamic_arr.push_back(200);
    
    // Menembus batas kapasitas, memicu realokasi memori heap baru
    std::cout << "Pushing 300 triggers geometric reallocation...\n";
    dynamic_arr.push_back(300);

    std::cout << "Cap Baru: " << dynamic_arr.capacity() 
              << ", Size Baru: " << dynamic_arr.size() << "\n";
    return 0;
}
```

---

### 10. Practical Example
Implementasi kelas Dynamic Array tingkat industri dengan growth factor 1.5, deteksi kapasitas, memory alignment, dan exception-safety:

```cpp
#include <iostream>
#include <memory>
#include <algorithm>
#include <stdexcept>
#include <utility>

template <typename T>
class IndustrialVector {
public:
    IndustrialVector() noexcept : data_(nullptr), size_(0), capacity_(0) {}

    explicit IndustrialVector(size_t initial_capacity) 
        : size_(0), capacity_(initial_capacity) {
        if (initial_capacity > 0) {
            data_ = allocate(capacity_);
        } else {
            data_ = nullptr;
        }
    }

    ~IndustrialVector() {
        clear();
        deallocate(data_, capacity_);
    }

    // Move semantics (Rule of Five)
    IndustrialVector(IndustrialVector&& other) noexcept
        : data_(other.data_), size_(other.size_), capacity_(other.capacity_) {
        other.data_ = nullptr;
        other.size_ = 0;
        other.capacity_ = 0;
    }

    IndustrialVector& operator=(IndustrialVector&& other) noexcept {
        if (this != &other) {
            clear();
            deallocate(data_, capacity_);
            data_ = other.data_;
            size_ = other.size_;
            capacity_ = other.capacity_;
            other.data_ = nullptr;
            other.size_ = 0;
            other.capacity_ = 0;
        }
        return *this;
    }

    // Disable copy for demonstrative simplicity and strictly deterministic resource control
    IndustrialVector(const IndustrialVector&) = delete;
    IndustrialVector& operator=(const IndustrialVector&) = delete;

    void push_back(const T& value) {
        ensure_capacity(size_ + 1);
        new (data_ + size_) T(value); // Placement new
        ++size_;
    }

    void push_back(T&& value) {
        ensure_capacity(size_ + 1);
        new (data_ + size_) T(std::move(value)); // Placement new with move
        ++size_;
    }

    T& operator[](size_t index) noexcept {
        return data_[index];
    }

    const T& operator[](size_t index) const noexcept {
        return data_[index];
    }

    size_t size() const noexcept { return size_; }
    size_t capacity() const noexcept { return capacity_; }

    void clear() noexcept {
        for (size_t i = 0; i < size_; ++i) {
            data_[i].~T(); // Explicit destruction
        }
        size_ = 0;
    }

private:
    T* data_;
    size_t size_;
    size_t capacity_;

    T* allocate(size_t n) {
        return static_cast<T*>(::operator new(n * sizeof(T)));
    }

    void deallocate(T* ptr, [[maybe_unused]] size_t n) noexcept {
        ::operator delete(ptr);
    }

    void ensure_capacity(size_t min_capacity) {
        if (min_capacity <= capacity_) return;

        // Growth Factor = 1.5x to prevent heap fragmentation
        size_t new_capacity = capacity_ + (capacity_ >> 1);
        if (new_capacity < min_capacity) {
            new_capacity = min_capacity;
        }
        if (new_capacity < 2) {
            new_capacity = 2;
        }

        T* new_data = allocate(new_capacity);

        // Move existing elements to uninitialized memory
        for (size_t i = 0; i < size_; ++i) {
            new (new_data + i) T(std::move_if_noexcept(data_[i]));
            data_[i].~T();
        }

        deallocate(data_, capacity_);
        data_ = new_data;
        capacity_ = new_capacity;
    }
};
```

---

### 11. Real World Example
**Studi Kasus: High-Frequency Trading (HFT) Order Book Depth & Apache Arrow**

Dalam arsitektur *columnar memory* seperti Apache Arrow atau mesin eksekusi order HFT:
Pemrosesan triliunan baris data memerlukan latensi ultra rendah. 
* Jika sebuah *Order Book* menyimpan list of pointer `Order*` (seperti `std::vector<Order*>`), traversal order akan memicu dereferensi pointer ke lokasi acak di heap (*pointer chasing*). Setiap lompatan pointer berisiko menghasilkan *L3 Cache Miss* dengan penalti latensi ~50-100 nanodetik.
* Sebaliknya, dengan menstrukturkan array sebagai flat memory kontigu:
  ```cpp
  struct FlatOrderBook {
      uint64_t order_ids[1024];
      uint32_t quantities[1024];
      double prices[1024];
  };
  ```
  CPU mengeksekusi *Hardware Prefetcher* secara optimal. Saat komputasi dilakukan pada `prices[0]`, CPU otomatis memuat `prices[1]` hingga `prices[7]` ke L1 Cache secara gratis melalui *SIMD Vectorization* (AVX2/AVX-512), menurunkan latensi kalkulasi total hingga $12\times$ lipat dibandingkan pendekatan pointer berantai.

---

### 12. Trade-offs

| Aspek | Dynamic Array | Singly/Doubly Linked List |
| :--- | :--- | :--- |
| **Random Access ($A[i]$)** | $O(1)$ deterministik via pointer math. | $O(N)$ linear traversal pointer dereference. |
| **Insertion at Tail** | $O(1)$ amortized (bisa $O(N)$ worst-case spike). | $O(1)$ deterministic (dengan tail pointer). |
| **Insertion at Head/Arbitrary** | $O(N)$ karena pergeseran memori (*memmove*).| $O(1)$ jika node pointer telah diketahui. |
| **Memory Overhead** | Rendah (hanya unused capacity padding). | Tinggi (8-16 bytes per node untuk metadata pointer).|
| **Cache Friendliness** | Maksimal (pola akses contiguous linear prefetch).| Sangat Buruk (fragmentasi heap menyebar luas). |
| **Resize Predictability** | Tidak menentu (ancaman tail latency saat realokasi).| Deterministik (biaya alokasi per node seragam). |

---

### 13. When To Use
* Operasi pembacaan data jauh lebih dominan dibanding penulisan di tengah/depan (Read-Heavy workloads).
* Ukuran dataset diketahui sebelumnya atau pertumbuhannya terprediksi sehingga pemanggilan `reserve()` dapat diaplikasikan.
* Algoritma membutuhkan akses indeks acak instan (Binary Search, Sorting, Sliding Window, Matrix Computations).
* Volume data masif yang membutuhkan efisiensi ruang memori tanpa overhead pointer tambahan.

---

### 14. When NOT To Use
* Dibutuhkan jaminan latensi operasi mutasi ketat (*hard real-time systems*) di mana lonjakan latensi (*jitter*) realokasi memori berordo $O(N)$ tidak dapat ditoleransi sama sekali.
* Sering melakukan operasi insersi atau delesi di awal (*head*) atau tengah koleksi (lebih baik gunakan `std::deque` atau `Circular Buffer`).
* Elemen data berukuran raksasa per unit (ratusan megabyte per objek), di mana biaya penyalinan memori saat relokasi heap akan melumpuhkan I/O bus sistem.

---

### 15. Common Mistakes
1. **Kegagalan Menggunakan `reserve()` Saat Ukuran Diketahui**: Menjalankan loop insersi jutaan elemen ke dynamic array kosong tanpa alokasi awal. Ini memicu puluhan kali siklus realokasi dan deallokasi heap berulang secara sia-sia.
2. **Pointer Invalidation Bug**: Menyimpan raw pointer atau iterator ke suatu elemen di dalam array dinamis, lalu melakukan `push_back()`. Ketika realokasi terjadi, pointer lama menjadi *dangling pointer* yang memicu *Undefined Behavior* (Segmentation Fault).
3. **Traversal Non-Lokal (Row-major vs Column-major)**:
   ```cpp
   // SALAH (Mengabaikan layout row-major: Cache thrashing parah)
   for (int col = 0; col < N; ++col)
       for (int row = 0; row < N; ++row)
           sum += matrix[row][col];

   // BENAR (Memanfaatkan spatial locality cache line)
   for (int row = 0; row < N; ++row)
       for (int col = 0; col < N; ++col)
           sum += matrix[row][col];
   ```

---

### 16. Best Practices (Production Checklist)
- [ ] Panggil `reserve(expected_size)` sesegera mungkin jika estimasi ukuran koleksi dapat dihitung secara logis.
- [ ] Utamakan `emplace_back` daripada `push_back` untuk mengkonstruksi objek kompleks secara in-place di heap tanpa membuat copy temporer.
- [ ] Hindari penyalinan vector secara tidak sengaja melalui pass-by-value; gunakan `const std::vector<T>&` atau `std::span<T>` (C++20).
- [ ] Pastikan destruktor kelas kustom yang disimpan di dynamic array bersifat `noexcept` agar `std::vector` dapat memilih alur optimasi `std::move_if_noexcept` alih-alih fallback ke deep copy lambat saat ekspansi buffer.
- [ ] Bebaskan kelebihan kapasitas yang tidak terpakai menggunakan teknik *shrink-to-fit* (`vec.shrink_to_fit()`) hanya jika array tersebut akan disimpan dalam status pasif untuk jangka waktu lama.

---

### 17. Troubleshooting
* **AddressSanitizer (ASan) Heap-Use-After-Free**: Sering terjadi saat referensi elemen diambil sebelum pemanggilan mutasi yang memicu realokasi.
  * *Diagnosis*: Jalankan compiler dengan flag `-fsanitize=address -g`.
  * *Solusi*: Jangan pernah mempertahankan referensi/pointer ke elemen array dinamis jika ada mutasi ukuran koleksi di dalam scope yang sama.
* **Over-allocation Out-Of-Memory (OOM)**:
  * *Penyebab*: Dynamic array melakukan ekspansi $\alpha = 2.0$ berulang pada ukuran raksasa (misal: array 16 GB melonjak meminta blok kontigu 32 GB baru, padahal RAM fisik yang tersisa hanya 20 GB).
  * *Solusi*: Gunakan custom allocator berpola *chunked/paged array* (`std::deque`) untuk payload raksasa guna memecah ketergantungan pada blok kontigu virtual memory raksasa.

---

### 18. Exercise
Selesaikan dua permasalahan algorithmic berikut dengan analisis kompleksitas mendalam:

1. **LeetCode 26: Remove Duplicates from Sorted Array**
   * *Instruksi*: Modifikasi array secara in-place sehingga elemen unik berada di bagian depan dengan memori tambahan $O(1)$. Jelaskan mengapa strategi contiguous memory menguntungkan arsitektur Two Pointers untuk kasus ini.
2. **Dynamic Subarray Sum Optimization**
   * *Instruksi*: Diberikan array bilangan bulat dinamis. Implementasikan kelas yang mampu melakukan `append(val)` dan query `rangeSum(left, right)` dalam waktu $O(1)$. Tentukan kompromi pemakaian memori antara struktur data tambahan yang Anda gunakan.

---

### 19. Challenge
Implementasikan struktur data **Thread-Safe Resizable Circular Buffer (Ring Buffer)** tanpa menggunakan lock global (menggunakan *Atomic Read/Write Pointers* dan memory order semantics `acquire-release`).
* Batasan: Buffer harus mampu memperluas kapasitasnya secara dinamis saat buffer penuh tanpa merusak konsistensi pembacaan data oleh thread *consumer* yang berjalan paralel.

---

### 20. Summary
* Array kontigu adalah satu-satunya struktur data fundamental yang menawarkan performa dereferensi $O(1)$ deterministik di tingkat instruksi perakitan prosesor berkat relasi linear *base address + offset*.
* Dynamic Array menukar kepastian waktu satu operasi penambahan dengan efisiensi sistem secara agregat melalui konsep *Amortized Analysis* ($O(1)$ amortized vs $O(N)$ worst-case).
* Cache Locality (L1/L2/L3) adalah faktor utama penentu performa eksekusi software modern. Struktur memori kontigu mendominasi linked structures karena memaksimalkan utilisasi unit pemrosesan CPU *Cache Lines* (64 bytes prefetching).
* Pemilihan growth factor ($\alpha = 1.5$ vs $\alpha = 2.0$) menentukan trade-off antara frekuensi alokasi ulang dan fragmentasi memori virtual di heap. Praktik terbaik produksi mewajibkan penggunaan pre-alokasi (`reserve`) untuk mengeliminasi alokasi yang tidak perlu.