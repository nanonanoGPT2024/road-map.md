## SEKSI 01 — IDENTITAS MODUL

| Parameter | Spesifikasi |
| :--- | :--- |
| **Kode Modul** | `DSA-0201` |
| **Nama Modul** | Struktur Data Linear: Static Array, Dynamic Array, dan Linked List |
| **Kategori** | `01-Core-Foundations` |
| **Tingkat Kesulitan** | Intermediate |
| **Prasyarat** | Pemrograman Prosedural/OOP Lanjut (C/C++ atau Rust direkomendasikan), Manajemen Memori Manual (Heap vs Stack), Notasi Asimtotik (Big-O, Big-$\Omega$, Big-$\Theta$) |
| **Estimasi Beban Kerja** | 8 – 10 Jam Pembelajaran Mandiri / Praktikum Laboratorium |
| **Target Pembaca** | Software Engineer, Systems Programmer, Computer Science Undergraduate, Backend Infrastructure Engineer |

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Karakteristik Memori Fisik (Bloom: C4 - Analyze)**: Membedakan representasi fisik memori antara struktur data berbasis alokasi kontigu (*contiguous*) dengan alokasi diskrit berbasis penunjuk (*scattered/node-based*) dalam hubungannya dengan hierarki memori CPU (*L1/L2/L3 Cache* dan *Spatial Locality*).
2. **Membuktikan Biaya Asimtotik Amortisasi (Bloom: C5 - Evaluate)**: Melakukan analisis biaya amortisasi (*Amortized Analysis*) menggunakan metode agregat (*aggregate method*) dan metode potensial (*potential method*) pada operasi `append` dalam dynamic array dengan variasi rasio ekspansi geometrik ($\alpha = 2$ vs $\alpha = 1.5$).
3. **Mengimplementasikan Struktur Data Linear Rendah Kesalahan (Bloom: C3 - Apply)**: Mengonstruksi implementasi *Singly Linked List*, *Doubly Linked List*, dan *Dynamic Array* dari nol (*from scratch*) dengan kepatuhan terhadap manajemen siklus hidup memori (alokasi, dealokasi, penanganan *memory leak*, dan pencegahan *dangling pointer*).
4. **Mengevaluasi Trade-Off Performa Struktural (Bloom: C5 - Evaluate)**: Memilih secara rasional antara varian array dan linked list untuk skenario produksi spesifik berdasarkan throughput akses acak (*random access*), beban mutasi (*insertion/deletion*), dan overhead metadata pointer per elemen.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
Struktur Data Linear
│
├── 1. Karakteristik Memori
│    ├── Alokasi Kontigu (Contiguous Memory Allocation)
│    └── Alokasi Diskrit Berbasis Node (Heap-Allocated Pointer/Reference)
│
├── 2. Ragam Array
│    ├── Static Array
│    │    ├── Ukuran Tetap di Waktu Kompilasi/Alokasi
│    │    └── Offset Calculation: Base + (Index * Element_Size)
│    └── Dynamic Array (e.g., std::vector, ArrayList)
│         ├── Kapasitas (Capacity) vs Ukuran (Size/Length)
│         ├── Strategi Reallokasi Geometrik (Amortized O(1))
│         └── Invalidation of Iterators/Pointers
│
└── 3. Ragam Linked List
     ├── Singly Linked List (SLL)
     │    └── Forward traversal (Node -> Next -> ...)
     ├── Doubly Linked List (DLL)
     │    ├── Bidirectional traversal (Prev <- Node -> Next)
     │    └── Sentinel Nodes (Dummy Head & Tail)
     └── Circular Linked List (CLL)
          └── Tail points back to Head
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pemahaman terhadap struktur data linear fundamental bukan sekadar menghafal antarmuka pemrograman aplikasi (API) standar seperti `std::vector` pada C++ atau `ArrayList` pada Java. Di balik abstraksi linearitas tersebut terdapat interaksi langsung dengan perangkat keras komputasi modern.

### Interaksi Arsitektur CPU Modern
Prosesor modern tidak membaca data dari RAM per satuan byte, melainkan dalam blok tetap yang disebut **Cache Line** (umumnya 64 byte pada arsitektur x86_64 dan ARM64).
1. **Spatial Locality**: Saat CPU mengakses elemen array $A[i]$, seluruh baris cache yang memuat elemen-elemen tetangga ($A[i+1]$, $A[i+2]$, dst.) otomatis di-cache ke dalam L1/L2 data cache. Ini menghasilkan *cache hit rate* mendekati optimal dan mengeksploitasi fitur *hardware prefetcher*.
2. **Pointer Chasing Penalty**: Pada Linked List, setiap simpul (*node*) dialokasikan secara independen di area heap. Dua node yang berurutan secara logis kemungkinan besar berada di alamat virtual memory yang saling berjauhan. Akses dari satu simpul ke simpul berikutnya memicu fenomena *pointer chasing*, menghasilkan serangkaian *L1/L2 cache misses*, dan memaksa core CPU mengeksekusi siklus *stall* sembari menunggu data diambil dari DRAM utama (sekitar 100-300 siklus siklus clock CPU per miss).

Dalam rekayasa perangkat lunak berkinerja tinggi—mulai dari mesin basis data, rendering mesin grafis, hingga sistem perdagangan frekuensi tinggi (*High-Frequency Trading*)—pemilihan yang keliru antara *Dynamic Array* dan *Linked List* dapat menurunkan performa hingga 1-2 orde magnitudo (*orders of magnitude*), meskipun kedua struktur data memiliki kompleksitas asimtotik logis yang sekilas identik.

---

## SEKSI 05 — APA ITU (WHAT)

Struktur Data Linear adalah koleksi elemen data yang disusun secara berurutan, di mana setiap elemen memiliki relasi satu-ke-satu dengan elemen sebelum (*predecessor*) dan sesudahnya (*successor*), kecuali elemen pertama dan terakhir.

### 1. Static Array
Struktur data berukuran tetap yang menempati blok memori fisik yang berdampingan (*contiguous memory block*). Ukuran ruang dialokasikan secara statis pada stack frame atau segmen data pada saat program diinisialisasi atau masuk ke cakupan fungsi.

### 2. Dynamic Array
Abstraksi di atas static array yang mendukung penambahan elemen tak terbatas secara konseptual. Struktur ini membungkus pointer ke array yang dialokasikan di heap, nilai kapasitas (*capacity*), dan jumlah elemen aktual (*size*). Ketika `size == capacity`, dynamic array mengalokasikan blok memori baru yang lebih besar, menyalin elemen lama, dan mendealokasikan blok sebelumnya.

### 3. Linked List
Koleksi struktur data diskrit (*node*) yang dihubungkan secara fungsional melalui penunjuk memori (*memory pointer* atau *reference*). Setiap node minimal menyimpan nilai payload data dan satu pointer ke node berikutnya.

* **Singly Linked List**: Node terdiri dari pasangan $(data, next)$.
* **Doubly Linked List**: Node terdiri dari tripel $(prev, data, next)$, memungkinkan penelusuran dua arah tanpa traversi ulang dari kepala (*head*).
* **Circular Linked List**: Node akhir (*tail*) menunjuk kembali ke node awal (*head*), menghilangkan pointer bernilai `nullptr`/`NULL`.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Perhitungan Alamat Array (Addressing Formula)
Untuk array satu dimensi berbasis indeks 0:
$$\text{Address}(A[i]) = \text{BaseAddress} + (i \times S)$$
Di mana:
* $\text{BaseAddress}$: Alamat byte pertama dari blok array ($A[0]$).
* $i$: Indeks elemen yang dicari ($0 \le i < N$).
* $S$: Ukuran representasi data tipe elemen dalam byte (`sizeof(T)`).

Operasi ini adalah evaluasi aritmatika tunggal, sehingga memiliki kompleksitas waktu absolut $\mathcal{O}(1)$ deterministik tanpa pencarian.

### 2. Mekanisme Reallokasi Dynamic Array & Analisis Amortisasi
Misalkan dynamic array dimulai dari kapasitas awal $C_0 = 1$ dengan rasio pertumbuhan $\alpha = 2$.
Operasi penyisipan ke-$N$ saat kapasitas penuh ($N = 2^k$):
1. Alokasi blok memori baru berukuran $2 \times N$.
2. Salin $N$ elemen dari blok lama ke blok baru: biaya operasional $N$.
3. Dealokasi memori blok lama.
4. Sisipkan elemen baru: biaya operasional $1$.

#### Pembuktian Amortisasi (Metode Agregat)
Total biaya $T(n)$ untuk melakukan $n$ operasi penambahan berturut-turut pada array yang awalnya kosong:
Biaya penulisan biasa: $n \times 1 = n$.
Biaya penyalinan saat resizing pada $i = 1, 2, 4, 8, \dots, 2^{\lfloor \log_2 n \rfloor}$:
$$\sum_{j=0}^{\lfloor \log_2 n \rfloor} 2^j = 2^{\lfloor \log_2 n \rfloor + 1} - 1 < 2n$$
Total biaya operasional:
$$T(n) = n + \sum \text{penyalinan} < n + 2n = 3n$$
Biaya per operasi tunggal yang diamortisasi (*amortized cost*):
$$\hat{c} = \frac{T(n)}{n} < \frac{3n}{n} = 3 = \mathcal{O}(1)$$

> **Catatan Arsitektur:** Faktor ekspansi $\alpha = 2$ umum digunakan pada GCC `libstdc++`, sedangkan $\alpha = 1.5$ digunakan pada MSVC STL dan folly `fbvector` untuk memungkinkan penggunaan kembali blok memori heap yang sebelumnya telah dibebaskan (*memory reuse*).

### 3. Manipulasi Pointer pada Linked List
Operasi mutasi pada linked list beroperasi secara eksklusif dengan mengubah arah penunjuk pointer, tanpa perlu memindahkan lokasi fisik data itu sendiri.

#### Penyisipan Node pada Singly Linked List (di antara Node $A$ dan Node $B$):
1. Inisialisasi node baru $N$.
2. Set $N \to next = A \to next$ (sekarang $N \to next$ merujuk ke $B$).
3. Set $A \to next = N$.
*Penting: Urutan tidak boleh dibalik. Jika $A \to next = N$ dieksekusi pertama kali, referensi ke $B$ hilang seketika (orphan memory/leak).*

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Perbandingan Layout Memori Fisik

```text
[STATIC / DYNAMIC ARRAY PADA MEMORI KONTIGU]
Base Address: 0x1000, sizeof(int) = 4 bytes
+------------+------------+------------+------------+
| A[0]: 42   | A[1]: 87   | A[2]: 19   | A[3]: 99   |
+------------+------------+------------+------------+
0x1000       0x1004       0x1008       0x100C        (Alamat fisik berurutan, 1 baris cache)

[LINKED LIST PADA HEAP MEMORY TERCACAH (POINTER CHASING)]
Node A                    Node B                    Node C
+-------+--------+       +-------+--------+       +-------+--------+
|Val: 42|Next:   |------>|Val: 87|Next:   |------>|Val: 19|Next: 0 |
|       | 0x8FA0 |       |       | 0x2140 |       |       | (NULL) |
+-------+--------+       +-------+--------+       +-------+--------+
Alamat: 0x0400           Alamat: 0x8FA0           Alamat: 0x2140
(Terdistribusi acak di heap; memerlukan 3x dereferensi memori yang independen)
```

### 2. Transisi Reallokasi Dynamic Array ($\alpha = 2$)

```text
Kondisi Awal: Capacity = 4, Size = 4 (Penuh)
Heap Block 1: [ 10 | 20 | 30 | 40 ] (Alamat: 0xAA00)
                     │
Append elemen 50 ───► Resizing terpicu!
                     │
1. Alokasi Heap Block 2: Kapasitas Baru = 8 (Alamat: 0xBB00)
   [ ? | ? | ? | ? | ? | ? | ? | ? ]
2. Salin Elemen:
   [ 10 | 20 | 30 | 40 | ? | ? | ? | ? ]
3. Sisipkan Elemen Baru (50):
   [ 10 | 20 | 30 | 40 | 50 | ? | ? | ? ] (Size = 5, Capacity = 8)
4. Dealokasi Heap Block 1 (0xAA00 dibebaskan)
```

### 3. Operasi Penyisipan Node pada Doubly Linked List

```text
Sebelum:
+--------+            +--------+
| Node A |<==========>| Node B |
+--------+            +--------+

Proses Penyisipan Node X di antara A dan B:
1. NodeX->next = NodeA->next       (NodeX->next menunjuk B)
2. NodeX->prev = NodeA             (NodeX->prev menunjuk A)
3. NodeA->next->prev = NodeX       (NodeB->prev menunjuk X)
4. NodeA->next = NodeX             (NodeA->next menunjuk X)

Sesudah:
+--------+            +--------+            +--------+
|        |<==========>|        |<==========>|        |
| Node A |            | Node X |            | Node B |
|        |<==========>|        |<==========>|        |
+--------+            +--------+            +--------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi Singly Linked List minimalis dalam bahasa C++ murni (standar ISO C++17) yang mendemonstrasikan manipulasi pointer eksplisit, traversing, dan pembersihan memori berbasis RAII (*Resource Acquisition Is Initialization*).

```cpp
#include <iostream>
#include <utility>

template <typename T>
class SimpleLinkedList {
private:
    struct Node {
        T data;
        Node* next;
        explicit Node(T val) : data(std::move(val)), next(nullptr) {}
    };

    Node* head;
    std::size_t length;

public:
    SimpleLinkedList() : head(nullptr), length(0) {}

    ~SimpleLinkedList() {
        clear();
    }

    // Mencegah shallow copy yang berbahaya bagi pointer mentah
    SimpleLinkedList(const SimpleLinkedList&) = delete;
    SimpleLinkedList& operator=(const SimpleLinkedList&) = delete;

    void push_front(T val) {
        Node* new_node = new Node(std::move(val));
        new_node->next = head;
        head = new_node;
        ++length;
    }

    bool pop_front(T& out_val) {
        if (!head) return false;
        
        Node* temp = head;
        out_val = std::move(temp->data);
        head = head->next;
        delete temp;
        --length;
        return true;
    }

    void clear() {
        Node* current = head;
        while (current != nullptr) {
            Node* next_node = current->next;
            delete current;
            current = next_node;
        }
        head = nullptr;
        length = 0;
    }

    [[nodiscard]] std::size_t size() const noexcept {
        return length;
    }

    void print() const {
        Node* curr = head;
        while (curr) {
            std::cout << curr->data << " -> ";
            curr = curr->next;
        }
        std::cout << "nullptr\n";
    }
};

int main() {
    SimpleLinkedList<int> list;
    list.push_front(30);
    list.push_front(20);
    list.push_front(10);

    // Output: 10 -> 20 -> 30 -> nullptr
    list.print();

    int removed_val;
    if (list.pop_front(removed_val)) {
        std::cout << "Removed: " << removed_val << "\n"; // 10
    }

    // Output: 20 -> 30 -> nullptr
    list.print();

    return 0;
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Implementasi produksi dari **Dynamic Vector** berkinerja tinggi dalam bahasa C++. Kode ini mengelola memori mentah (*raw uninitialized memory*) secara manual menggunakan operator `new unsigned char[]` dan `placement new`, guna mencegah instansiasi objek default yang sia-sia, mencerminkan cara kerja internal `std::vector`.

```cpp
#include <iostream>
#include <memory>
#include <new>
#include <utility>
#include <stdexcept>

template <typename T>
class Vector {
private:
    T* data_;
    std::size_t capacity_;
    std::size_t size_;

    void reallocate(std::size_t new_capacity) {
        // Alokasikan raw memory tanpa memanggil konstruktor T
        auto* new_block = static_cast<T*>(::operator new(new_capacity * sizeof(T)));

        // Pindahkan elemen yang ada ke buffer baru menggunakan move semantic
        for (std::size_t i = 0; i < size_; ++i) {
            new (&new_block[i]) T(std::move(data_[i]));
            data_[i].~T(); // Destruksi objek pada buffer lama
        }

        // Dealokasi raw memory lama
        ::operator delete(data_);
        data_ = new_block;
        capacity_ = new_capacity;
    }

public:
    Vector() noexcept : data_(nullptr), capacity_(0), size_(0) {}

    explicit Vector(std::size_t initial_cap) : capacity_(initial_cap), size_(0) {
        data_ = static_cast<T*>(::operator new(capacity_ * sizeof(T)));
    }

    ~Vector() {
        clear();
        ::operator delete(data_);
    }

    Vector(const Vector&) = delete;
    Vector& operator=(const Vector&) = delete;

    Vector(Vector&& other) noexcept 
        : data_(other.data_), capacity_(other.capacity_), size_(other.size_) {
        other.data_ = nullptr;
        other.capacity_ = 0;
        other.size_ = 0;
    }

    void push_back(const T& value) {
        if (size_ == capacity_) {
            reallocate(capacity_ == 0 ? 1 : capacity_ * 2);
        }
        new (&data_[size_]) T(value);
        ++size_;
    }

    void push_back(T&& value) {
        if (size_ == capacity_) {
            reallocate(capacity_ == 0 ? 1 : capacity_ * 2);
        }
        new (&data_[size_]) T(std::move(value));
        ++size_;
    }

    void pop_back() {
        if (size_ == 0) return;
        --size_;
        data_[size_].~T();
    }

    void clear() noexcept {
        for (std::size_t i = 0; i < size_; ++i) {
            data_[i].~T();
        }
        size_ = 0;
    }

    [[nodiscard]] std::size_t size() const noexcept { return size_; }
    [[nodiscard]] std::size_t capacity() const noexcept { return capacity_; }

    T& operator[](std::size_t index) noexcept {
        return data_[index]; // Fast unbounds-checked access
    }

    const T& operator[](std::size_t index) const noexcept {
        return data_[index];
    }

    T& at(std::size_t index) {
        if (index >= size_) {
            throw std::out_of_range("Vector::at: index out of bounds");
        }
        return data_[index];
    }
};

int main() {
    Vector<std::string> str_vec;
    str_vec.push_back("High-Throughput");
    str_vec.push_back("Engineered");
    str_vec.push_back("Systems");

    std::cout << "Size: " << str_vec.size() << ", Cap: " << str_vec.capacity() << "\n";

    for (std::size_t i = 0; i < str_vec.size(); ++i) {
        std::cout << "Index [" << i << "]: " << str_vec[i] << "\n";
    }

    return 0;
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Memilih antara Static Array, Dynamic Array, dan Linked List menuntut evaluasi trade-off komputasi dan konsumsi memori berikut:

| Operasi / Metrik | Static Array | Dynamic Array | Singly Linked List | Doubly Linked List |
| :--- | :--- | :--- | :--- | :--- |
| **Akses Acak (`[i]`)** | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ |
| **Penyisipan di Head** | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ |
| **Penyisipan di Tail** | N/A (Ukuran Statis) | Amortized $\mathcal{O}(1)$ / Worst $\mathcal{O}(n)$ | $\mathcal{O}(1)$ (jika pegang tail) | $\mathcal{O}(1)$ |
| **Penyisipan di Tengah** | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ | $\mathcal{O}(1)^*$ | $\mathcal{O}(1)^*$ |
| **Pencarian Data (Linear)** | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ |
| **Pencarian Data (Sorted)** | $\mathcal{O}(\log n)$ (Binary Search) | $\mathcal{O}(\log n)$ | $\mathcal{O}(n)$ (Tidak bisa binary search) | $\mathcal{O}(n)$ |
| **Overhead Memori** | $0$ byte tambahan | Cadangan kapasitas ($Cap - Size$) | $1 \text{ ptr}$ per elemen ($8$ byte pd 64-bit) | $2 \text{ ptr}$ per elemen ($16$ byte pd 64-bit) |
| **Pemanfaatan Cache** | **Sangat Tinggi** | **Sangat Tinggi** | **Buruk** | **Sangat Buruk** |

$^*$*Catatan: $\mathcal{O}(1)$ dengan asumsi pointer iterator ke posisi yang diinginkan telah didapatkan sebelumnya.*

### Analisis Paradoks Teoretis vs Realitas Perangkat Keras
Secara teoretis, Linked List tampak superior untuk kasus modifikasi (*insertion/deletion*) di bagian acak. Namun dalam praktiknya:
* Untuk menyisipkan data pada node ke-$K$, Anda harus melintasi $K-1$ node terlebih dahulu ($\mathcal{O}(K)$ pointer traversing).
* Array membutuhkan pergeseran memori (*memmove/memcpy*), tetapi pergeseran data kontigu dilakukan menggunakan instruksi vector SIMD (misalnya AVX-512) yang sangat cepat. Akibatnya, pada kumpulan data kecil hingga menengah ($N < 50.000$), Dynamic Array sering kali mengungguli Linked List bahkan untuk operasi penyisipan acak.

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan `reserve()` di Awal (Dynamic Array)**: Jika batas perkiraan elemen diketahui, panggil cadangan alokasi terlebih dahulu untuk mengeliminasi alokasi ulang dan penyalinan memori berkali-kali.
2. **Prioritaskan Dynamic Array sebagai Default**: Menurut Bjarne Stroustrup, default container haruslah `std::vector` (Dynamic Array) kecuali ada justifikasi arsitektural yang mewajibkan linked list (misalnya mutasi node tanpa pembatalan pointer/referensi lain).
3. **Gunakan Sentinel Nodes (Dummy Nodes) pada Linked List**: Terapkan dummy head dan dummy tail untuk mengeliminasi edge-case percabangan kode (`if (head == nullptr)` atau `if (curr->next == nullptr)`), sehingga mengurangi risiko *branch misprediction* dan memangkas kompleksitas logika penulisan pointer.
4. **Pencegahan Memory Leak Pasca Pemisahan**: Saat memotong rantai pointer pada linked list, simpan alamat node yang diputus dalam variabel temporer sebelum memindahkan pointer referensi utama, lalu segera dealokasikan.
5. **Waspadai Iterator Invalidation**: Pada Dynamic Array, operasi `push_back` atau penyisipan lain yang memicu relokasi buffer internal akan membuat semua raw pointer, referensi, dan iterator ke elemen lama menjadi tidak valid (*dangling references*).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Invalidation Pointer / Dangling Reference pada Dynamic Array
```cpp
std::vector<int> vec = {10, 20, 30};
int& ref = vec[0];
vec.push_back(40); // Jika alokasi ulang terjadi, memory lama di-dealokasikan!
std::cout << ref;  // UNDEFINED BEHAVIOR: Membaca alamat memori yang telah dibebaskan.
```

### 2. Hilangnya Referensi Node (Memory Leak & Orphan Chain)
```cpp
// SALAH: Kehilangan alamat node berikutnya
void bad_insert(Node* current, int val) {
    Node* new_node = new Node(val);
    current->next = new_node;        // Pointer ke sisa rantai list HILANG!
    new_node->next = current->next;  // new_node menunjuk ke dirinya sendiri
}

// BENAR:
void good_insert(Node* current, int val) {
    Node* new_node = new Node(val);
    new_node->next = current->next;
    current->next = new_node;
}
```

### 3. Mengabaikan Overhead Alokator Heap pada Linked List
Banyak engineer mengabaikan bahwa alokasi heap via `malloc` atau `new` memiliki metadata overhead internal (biasanya 8–16 byte per chunk alokasi oleh glibc ptmalloc). Node integer `sizeof(int) = 4` pada Singly Linked List arsitektur 64-bit:
* Payload: 4 byte (+ 4 byte padding alignment) = 8 byte
* Pointer next: 8 byte
* Heap metadata chunk overhead: 16 byte
* **Total konsumsi memori per 1 integer: 32 byte!** (Efisiensi penggunaan data hanya $4/32 = 12.5\%$).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: In-place Array Reversal (Tingkat: Easy)
* **Deskripsi**: Diberikan sebuah static buffer berukuran $N$. Balik susunan elemen array tersebut secara langsung tanpa membuat array sekunder (In-place, ruang $\mathcal{O}(1)$).
* **Syarat**: Algoritma harus berjalan dalam $\mathcal{O}(n)$ time complexity dan bertukar elemen menggunakan teknik dua penunjuk (*two pointers*).
* **Test Case**:
  * Input: `[1, 2, 3, 4, 5]` $\to$ Output: `[5, 4, 3, 2, 1]`
  * Input: `[42]` $\to$ Output: `[42]`
  * Input: `[]` $\to$ Output: `[]`

### Latihan 2: Floyd's Cycle-Finding Algorithm (Tingkat: Medium)
* **Deskripsi**: Buat fungsi pendeteksi siklus pada Singly Linked List. Jika terdapat siklus, kembalikan alamat memori node pertama tempat siklus dimulai. Jika tidak ada siklus, kembalikan `nullptr`.
* **Batasan**: Dilarang memodifikasi nilai node dan dilarang menggunakan struktur data hash set/pencatat memori tambahan (Space complexity harus ketat $\mathcal{O}(1)$).
* **Test Case**:
  * List: `1 -> 2 -> 3 -> 4 -> 2` (4 kembali ke 2) $\to$ Output: Node dengan nilai `2`.
  * List: `1 -> 2 -> 3 -> nullptr` $\to$ Output: `nullptr`.

### Latihan 3: Implementasi Circular Buffer Berbasis Dynamic Array (Tingkat: Hard)
* **Deskripsi**: Bangun struktur data `CircularRingBuffer` dengan API:
  * `push(T item)`: Jika kapasitas penuh, otomatis lakukan resize $2\times$ kapasitas awal tanpa merusak urutan FIFO.
  * `pop()`: Mengambil data tertua secara $\mathcal{O}(1)$.
* **Tantangan**: Saat terjadi operasi reallokasi pada circular buffer, posisi pointer internal `head` dan `tail` kemungkinan tidak berada pada awal array linear (telah terjadi *wrap-around*). Rekonstruksi urutan data tersebut dengan benar pada buffer baru.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Sebuah sistem 64-bit mengeksekusi iterasi traversal pada 1.000.000 data integer (32-bit). Struktur data A menggunakan `Dynamic Array`, struktur data B menggunakan `Singly Linked List`. Mengapa struktur data A hampir selalu 10x-50x lebih cepat dibanding B pada CPU modern?**
   * A) Array memiliki kompleksitas $\mathcal{O}(\log n)$, linked list $\mathcal{O}(n)$.
   * B) Linked list membutuhkan dereferensi pointer yang menyebabkan seringnya cache miss dan instruksi serial stall, sedangkan alokasi kontigu array memaksimalkan pemanfaatan L1/L2 data cache lines serta hardware prefetching.
   * C) Array disimpan di stack memory, sedangkan linked list selalu berada di registri prosesor.
   * D) Ukuran byte integer pada dynamic array dikompresi oleh CPU.
   * *Jawaban yang benar:* **B**. Penjelasan: Kontiguitas memori memicu hardware memory prefetcher mengisi CPU Cache Line (64 byte) sebelum data diminta, sedangkan traversing list melompat ke alamat acak di RAM yang berbiaya latensi DRAM tinggi.

2. **Berapakah amortized cost dari operasi penyisipan elemen pada Dynamic Array jika kita memilih strategi penambahan kapasitas berupa konstan aritmatika ($C_{\text{new}} = C_{\text{old}} + 1000$) alih-alih pengali geometrik ($C_{\text{new}} = C_{\text{old}} \times 2$)?**
   * A) Tetap $\mathcal{O}(1)$
   * B) $\mathcal{O}(\log n)$
   * C) $\mathcal{O}(n)$
   * D) $\mathcal{O}(n^2)$
   * *Jawaban yang benar:* **C**. Penjelasan: Jika kapasitas bertambah secara aritmatika konstan, untuk mencapai ukuran $N$ diperlukan $N/k$ kali alokasi ulang. Total biaya penyalinan membentuk deret aritmatika: $\sum i \cdot k \approx \mathcal{O}(n^2)$. Dibagi dengan $N$ operasi, biaya rata-rata per operasi menjadi $\mathcal{O}(n)$, membatalkan efisiensi amortisasi.

3. **Operasi mana yang memiliki kompleksitas waktu $\mathcal{O}(1)$ pada Singly Linked List standar yang HANYA memegang pointer `head`?**
   * A) Menghapus elemen terakhir (*tail deletion*).
   * B) Menyisipkan elemen di posisi terdepan (*prepend/insert at head*).
   * C) Mengambil elemen pada indeks ke-$K$.
   * D) Membalik urutan list secara keseluruhan (*in-place reverse*).
   * *Jawaban yang benar:* **B**. Penjelasan: Menyisipkan di head hanya memerlukan alokasi node baru, mengarahkan `new_node->next = head`, dan memindahkan `head = new_node`. Tidak ada penelusuran (traversal) yang diperlukan.

4. **Kelemahan terbesar penggunaan rasio ekspansi $\alpha = 2$ pada sistem operasi virtual memory tertentu dibanding $\alpha = 1.5$ atau rasio emas ($\phi \approx 1.618$) adalah:**
   * A) Rasio 2 membutuhkan operasi floating-point saat menghitung ukuran baru.
   * B) Setiap blok memori baru berukuran $2^k$ selalu lebih besar daripada total akumulasi seluruh blok memori lama yang pernah dibebaskan ($\sum_{i=0}^{k-1} 2^i = 2^k - 1 < 2^k$), sehingga alokator sistem tidak pernah dapat menggunakan kembali memori chunk yang lama.
   * C) Menghasilkan performa cache alignment yang buruk pada kartu grafis.
   * D) Kompleksitas asimtotik amortisasinya turun menjadi $\mathcal{O}(\sqrt{n})$.
   * *Jawaban yang benar:* **B**. Penjelasan: Ini adalah temuan fundamental memory allocator: dengan rasio 2, blok memori sebelumnya tidak akan pernah cukup besar untuk menampung alokasi berikutnya, memperparah fragmentasi memori.

5. **Apa fungsi dari Dummy Sentinel Node pada Doubly Linked List?**
   * A) Menyimpan metadata ukuran total array untuk akses $\mathcal{O}(1)$.
   * B) Menghilangkan pengecekan kondisi batas pointer null pada saat menyisipkan atau menghapus simpul di awal atau akhir rantai.
   * C) Menjamin semua memori terfragmentasi secara teratur.
   * D) Memungkinkan penelusuran multithread tanpa penguncian (lock-free).
   * *Jawaban yang benar:* **B**. Penjelasan: Sentinel bertindak sebagai pembatas permanen sehingga setiap node valid selalu diapit oleh dua node lainnya. Hal ini memangkas percabangan logika penanganan `nullptr` di seluruh method mutasi.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

### Literatur Akademik & Buku Teks
1. Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to Algorithms* (4th ed.). MIT Press. — **Bab 10: Elementary Data Structures & Bab 17: Amortized Analysis**.
2. Knuth, D. E. (1997). *The Art of Computer Programming, Volume 1: Fundamental Algorithms* (3rd ed.). Addison-Wesley. — **Seksi 2.2: Linear Lists**.
3. Drepper, U. (2007). *What Every Programmer Should Know About Memory*. Red Hat, Inc. — Pembahasan mendalam mengenai cache hit, miss penalty, dan layout memori linear.

### Artikel Teknis & Dokumentasi Mesin Produksi
1. Folly (Facebook Open-source Library) Documentation: `folly::fbvector` — Rationale on why $\alpha = 1.5$ is superior to $\alpha = 2$ for memory allocation patterns.
2. Bjarne Stroustrup (2012). *Keynote: GoingNative 2012 – Why you should avoid Linked Lists for Performance*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* Struktur data linear mengatur elemen data dalam hubungan sekuensial logis, namun implementasi fisik memorinya terbagi menjadi dua kategori ekstrem: **Kontigu** (Array) dan **Diskrit Berbasis Node** (Linked List).
* **Static Array** menawarkan determinisme alokasi dan efisiensi akses acak $\mathcal{O}(1)$ mutlak, namun dibatasi oleh fleksibilitas ukuran yang kaku.
* **Dynamic Array** menyelesaikan kendala ukuran dengan menyediakan amortized $\mathcal{O}(1)$ penambahan data melalui strategi alokasi ulang geometrik ($\alpha > 1$), sambil tetap mempertahankan keunggulan *spatial cache locality*.
* **Linked List** memprioritaskan kemudahan penataan ulang pointer secara struktural dengan biaya alokasi independen, kehilangan kemampuan pengindeksan acak, penalti fragmentasi memori, serta overhead ukuran pointer pada setiap elemennya.
* Pemilihan struktur data modern harus dipandu oleh pemahaman karakteristik cache CPU; kriteria bukan lagi sekadar batasan teoritis kompleksitas Big-O tingkat tinggi, melainkan minimasi *cache misses* dan *pointer chasing*.

---

## SEKSI 17 — GLOSARIUM

* **Cache Line**: Satuan blok transfer data terkecil antara memori utama (RAM) dan cache prosesor, umumnya berukuran 64 byte.
* **Spatial Locality**: Prinsip arsitektur di mana pemanggilan satu lokasi memori fisik meningkatkan probabilitas lokasi memori di dekatnya akan diakses dalam waktu singkat.
* **Pointer Chasing**: Kondisi di mana prosesor harus membaca alamat memori dari sebuah pointer sebelum dapat mengeksekusi pembacaan alamat berikutnya, menciptakan latensi serial pada memori tak kontigu.
* **Amortized Analysis**: Metode penaksiran performa algoritma yang meratakan biaya eksekusi dari operasi terburuk yang jarang terjadi ke seluruh rangkaian deret operasi.
* **Sentinel Node**: Node tiruan (*dummy node*) tanpa data payload yang diposisikan di ujung list untuk menyederhanakan penanganan kasus batas (*edge case*) pembaruan pointer.
* **Geometric Resizing**: Strategi pelipatgandaan kapasitas internal dynamic array dengan faktor pengali konstan ($\alpha$) untuk mempertahankan efisiensi rata-rata penambahan data berkesinambungan.
* **Iterator Invalidation**: Kerusakan integritas objek penunjuk/iterator akibat realokasi memori kontainer di balik layar yang mendestruksi blok memori lama.
* **Placement New**: Konstruksi bahasa C++ yang menginisialisasi objek pada alamat blok memori mentah yang telah dialokasikan sebelumnya tanpa meminta alokasi baru dari heap.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Penekanan Materi
* Tekankan kepada mahasiswa/peserta didik bahwa kompleksitas $\mathcal{O}(1)$ pada operasi penyisipan linked list sering kali disalahpahami.linked list hanya $\mathcal{O}(1)$ jika pointer sudah berada di target mutasi. Menemukan posisi tersebut tetap memakan biaya $\mathcal{O}(n)$.
* Selenggarakan demonstrasi benchmark waktu nyata (*live benchmark*) yang membandingkan penelusuran `std::vector<int>` vs `std::list<int>` pada ukuran 100.000 elemen untuk memperlihatkan efek nyata dari *cache locality*.

### Perangkap Mental Peserta Didik
* Sering berasumsi bahwa "Linked List selalu lebih cepat untuk memasukkan data dibanding Array karena tidak perlu geser elemen". Ingatkan kembali bahwa *shifting memory* menggunakan instruksi blok vectorized sangat cepat, sedangkan dereferensi pointer ke heap liar memicu *stall* eksekusi CPU puluhan hingga ratusan cycle.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal Rilis | Penulis / Reviewer | Deskripsi Perubahan |
| :--- | :--- | :--- | :--- |
| `v1.0.0` | 2025-01-15 | Senior Technical Curriculum Architect | Rilis kurikulum awal: Komprehensif 20 Seksi Standar GEMINI.md |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `DSA-0102` — Analisis Kompleksitas Asimtotik Lanjut dan Model Komputasi
* **Modul Berikutnya**: `DSA-0202` — Struktur Data Linear Khusus: Stack, Queue, dan Deque Berperforma Tinggi
* **Indeks Modul**: Kategori `01-Core-Foundations` / Bab 02: Struktur Data Linear Fundamental