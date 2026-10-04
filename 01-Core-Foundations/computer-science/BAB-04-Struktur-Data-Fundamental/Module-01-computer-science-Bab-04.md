# Kategori: 01-Core-Foundations
# Jalur: Computer Science
# Bab 04: Struktur Data Fundamental
# Modul 01: Representasi Memori, Array Statis, Dynamic Array, dan Linked List

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** CS-FND-0401
* **Nama Modul:** Representasi Memori, Array Statis, Dynamic Array, dan Linked List: Prinsip Desain, Analisis Amortisasi, dan Efisiensi Hardware
* **Level Kategori:** Core Foundations (CS Undergraduate / Systems Engineering Track)
* **Prasyarat:**
  * Pengetahuan dasar pemrograman prosedural (C atau C++)
  * Pemahaman arsitektur komputer dasar: Register, CPU Cache (L1/L2/L3), RAM, Stack vs Heap
  * Analisis Asimptotik Dasar: Notasi Big-O, Big-$\Omega$, Big-$\Theta$
* **Estimasi Waktu Belajar:** 8–10 Jam (Teori, Bedah Assembly/Memori, Implementasi Bare-Metal, dan Latihan Algoritmik)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis (C4)** pemetaan memori fisik dan virtual dari struktur data linear terhadap arsitektur CPU *cache hierarchy* dan implikasinya terhadap *spatial locality*.
2. **Mengevaluasi (C5)** kompleksitas komputasi dan memori antara struktur data berbasis alokasi kontigu (*contiguous*) vs berbasis simpul (*node-based/scattered*).
3. **Mengembangkan (C6)** implementasi *Dynamic Array* dari *scratch* dengan strategi ekspansi geometris (*geometric resizing*) serta membuktikan analisis biaya amortisasinya ($O(1)$ *amortized time*) melalui *Aggregate Method* dan *Banker’s/Accounting Method*.
4. **Mengonstruksi (C6)** struktur data *Singly Linked List* dan *Doubly Linked List* yang robust, mencakup manipulasi *pointer* tingkat rendah, penggunaan *sentinel nodes* (dummy head/tail), dan manajemen memori manual tanpa kebocoran (*memory leak*).
5. **Mendiagnosis (C4)** degradasi performa akibat *cache misses*, *pointer chasing*, dan fragmentasi *heap* pada aplikasi berskala intensif memori.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       MEMORI LINIER SISTEM KOMPUTER
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼                                                 ▼
   ALOKASI KONTIGU                                   ALOKASI TERPISAH
 (Contiguous Allocation)                         (Scattered Heap-Allocated)
           │                                                 │
     ┌─────┴──────────────┐                                  ▼
     ▼                    ▼                             LINKED LIST
ARRAY STATIS        DYNAMIC ARRAY                            │
(Fixed-size,        (Geometric Resizing,             ┌───────┴───────┐
 Stack/Data Seg)     Heap-Allocated Buffer)          ▼               ▼
     │                    │                     SINGLY-LINKED   DOUBLY-LINKED
     │                    │                     (Next Pointer)  (Next & Prev)
     │                    │                          │               │
     └──────────┬─────────┘                          └───────┬───────┘
                │                                            │
                ▼                                            ▼
   Hardware Synergy:                                Hardware Penalty:
   • High Spatial Locality                          • Pointer Chasing
   • O(1) Indexing Calculation                      • Low Cache Locality
   • Cache Line Prefetching Friendly                • Memory Overhead per Node
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pemilihan struktur data linear bukan sekadar keputusan sintaksis antara menggunakan kurung siku `[]` atau pointer referensi `->next`. Pada arsitektur perangkat keras modern, kecepatan siklus komputasi CPU jauh melampaui latensi akses memori utama (RAM)—fenomena yang dikenal sebagai *Memory Wall*. Akses ke register memakan waktu $< 1 \text{ ns}$, CPU Cache L1 sekitar $1 \text{ ns}$, sedangkan akses ke DRAM memakan waktu $50\text{--}100 \text{ ns}$.

Ketika data disusun secara berurutan (*contiguous*) seperti pada **Array**, mekanisme CPU *Hardware Prefetcher* dapat memuat blok data berikutnya ke dalam *Cache Line* (umumnya 64 byte) sebelum CPU secara eksplisit memintanya. Hal ini menghasilkan lonjakan performa berlipat ganda (*spatial locality*). Sebaliknya, **Linked List** memetakan simpul-simpulnya secara acak pada *heap memory*. Setiap navigasi ke elemen berikutnya memicu apa yang disebut *pointer chasing*, yang hampir selalu menghasilkan *cache miss* dan memaksa CPU untuk mengalami *stall cycle*.

Memahami struktur data fundamental dari tingkat representasi memori adalah fondasi utama untuk:
* Merancang algoritma berkecepatan tinggi (*latency-critical engines* seperti game loop, high-frequency trading, DBMS index).
* Menghindari perangkap alokasi naif yang mengakibatkan degradasi asimptotik menjadi kuadratik ($O(N^2)$) pada saat *array growth*.
* Memahami cara runtime modern (seperti V8, JVM, atau C++ STL) mengimplementasikan tipe data bawaan seperti `std::vector`, `ArrayList`, atau `slices`.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Array Statis (*Static Array*)
Array statis adalah blok memori kontinu berukuran tetap yang menampung sekumpulan elemen bertipe homogen. Ukuran alokasi ditentukan saat *compile-time* (jika dialokasikan di *stack* atau segmen data BSS) dan tidak dapat diubah sepanjang siklus hidup eksekusi program.

### 2. Dynamic Array (*Resizable Array / Vector*)
Dynamic Array adalah abstraksi di atas array statis yang dialokasikan di *heap memory*. Struktur ini menyediakan antarmuka ukuran dinamis (*resizable*). Ketika kapasitas maksimum buffer tercapai, sistem secara otomatis:
1. Mengalokasikan blok memori baru yang lebih besar (biasanya faktor pengali $g = 1.5$ atau $g = 2.0$).
2. Menyalin (*deep copy*) seluruh elemen dari buffer lama ke buffer baru.
3. Mendealokasikan buffer lama untuk mencegah kebocoran memori.
4. Mengarahkan pointer basis data ke buffer baru.

### 3. Singly Linked List (Daftar Terhubung Tunggal)
Koleksi elemen linier yang disebut *nodes* (simpul). Tiap simpul terbagi menjadi dua bagian: *data payload* dan sebuah pointer `next` yang mereferensikan alamat memori dari simpul berikutnya. Simpul terakhir menunjuk ke pointer `NULL`/`nullptr`.

### 4. Doubly Linked List (Daftar Terhubung Ganda)
Pengembangan dari Singly Linked List di mana setiap simpul memiliki tiga komponen: *data payload*, pointer `next` ke simpul penerus, dan pointer `prev` ke simpul pendahulu. Hal ini memungkinkan traversal dua arah secara simetris, namun meningkatkan *overhead* memori sebesar satu pointer per simpul.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Matematika Pengalamatan Array (Contiguous Address Formula)

Array memiliki properti akses acak berkecepatan $O(1)$ murni karena alamat memori elemen ke-$i$ dapat dihitung secara instan melalui aritmetika pointer tanpa iterasi:

$$\text{Address}(A[i]) = \text{BaseAddress} + (i \times \text{SizeOfElement})$$

Untuk array multidimensi 2D dengan dimensi $M \times N$ bertipe Row-Major (seperti pada C/C++):

$$\text{Address}(A[r][c]) = \text{BaseAddress} + \big((r \times N) + c\big) \times \text{SizeOfElement}$$

CPU hanya perlu mengeksekusi satu instruksi mesin *base-plus-offset* (seperti `mov rax, [rbx + rcx*4]`), menjadikannya salah satu operasi paling efisien dalam arsitektur Von Neumann.

### 2. Teorema Amortisasi Dynamic Array (Geometric vs Arithmetic Resizing)

Mengapa ukuran dynamic array digandakan ($C \times 2$) dan bukan ditambah konstan ($C + K$)?

* **Ekspansi Aritmetik ($+K$):**
  Jika buffer bertambah sebanyak konstan $K$ setiap kali penuh, maka untuk memasukkan $N$ elemen, program akan melakukan pemindahan data sebanyak:
  $$\sum_{j=1}^{N/K} j \cdot K = K \frac{(N/K)(N/K + 1)}{2} \approx \frac{N^2}{2K} = O(N^2)$$
  Rata-rata biaya per operasi penyisipan adalah $\frac{O(N^2)}{N} = O(N)$. Ini tidak efisien.

* **Ekspansi Geometrik ($\times 2$):**
  Kapasitas melipatgandakan diri: $1, 2, 4, 8, \dots, 2^{\lceil \log_2 N \rceil}$. Operasi alokasi ulang dan penyalinan data hanya terjadi pada langkah $2^k$. Total operasi penyalinan elemen untuk memasukkan $N$ elemen adalah:
  $$\sum_{j=0}^{\lfloor \log_2 N \rfloor} 2^j = 2^{\lfloor \log_2 N \rfloor + 1} - 1 < 2N = O(N)$$
  Biaya total penyisipan $N$ elemen adalah $N$ (biaya penulisan reguler) $+ 2N$ (biaya penyalinan ekspansi) $= 3N$. 
  
  Maka, rata-rata biaya per penyisipan adalah:
  $$\text{Amortized Cost} = \frac{3N}{N} = O(1)$$

#### Pembuktian Metode Akuntansi (Banker's Method)
Asumsikan biaya riil satu penulisan elemen adalah $1 \text{ koin}$. 
Kita tetapkan tarif pajak amortisasi sebesar $3 \text{ koin}$ per operasi `push_back`:
1. **1 koin** digunakan langsung untuk membayar operasi penulisan data baru ke memori.
2. **1 koin** disimpan sebagai saldo kredit pada posisi data tersebut.
3. **1 koin** disimpan sebagai saldo kredit untuk membantu elemen pasangan lama yang sudah tidak memiliki kredit.

Ketika array dengan kapasitas $K$ telah terisi penuh, telah terkumpul dana amortisasi cadangan sebesar $2 \times (K/2) = K \text{ koin}$. Seluruh koin ini mencukupi tepat untuk membiayai penyalinan $K$ elemen lama ke array baru tanpa memerlukan injeksi sumber daya komputasi tambahan. Dengan demikian, biaya teramortisasi per operasi terbukti $O(1)$.

### 3. Mutasi Pointer pada Linked List

Struktur node-based mengabaikan pengindeksan acak demi fleksibilitas mutasi simpul lokal dengan biaya $O(1)$ apabila pointer target telah diketahui.

#### Penyisipan Node pada Singly Linked List:
```
1. Buat node baru: Node* P = allocate(value)
2. P->next = TargetPrev->next
3. TargetPrev->next = P
(Urutan eksekusi langkah 2 dan 3 TIDAK BOLEH dibalik untuk menghindari terputusnya rantai memori)
```

#### Penggunaan Sentinel Nodes (Dummy Head & Tail)
Pada Linked List konvensional, operasi penyisipan dan penghapusan selalu memerlukan pengecekan kondisi batas:
```c
if (head == NULL) { ... }
if (node == head) { ... }
```
Dengan menerapkan **Sentinel Nodes** (simpul dummy permanen yang tidak menampung data aplikatif), semua node yang sebenarnya dijamin selalu memiliki tetangga *prev* dan *next*. Ini mengeliminasi seluruh percabangan kondisi batas (*edge-case conditional branches*) di tingkat perakitan mesin.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Peta Memori: Contiguous Array vs Scattered Linked List

```
SKENARIO A: ARRAY KONTIGU DI DALAM RAM
Basis: 0x1000, Tipe: uint32_t (4 byte)

Alamat:  0x1000   0x1004   0x1008   0x100C   0x1010   0x1014
         ┌────────┬────────┬────────┬────────┬────────┬────────┐
Data:    │   42   │   88   │   12   │   99   │   05   │   31   │
Indeks:  │  A[0]  │  A[1]  │  A[2]  │  A[3]  │  A[4]  │  A[5]  │
         └────────┴────────┴────────┴────────┴────────┴────────┘
         ▲                                            ▲
         └───────────── Satu Baris Cache Line ────────┘
           (Dimuat sekaligus ke Cache L1 dalam 1 siklus memori)


SKENARIO B: LINKED LIST TERISOLASI DI DALAM HEAP (POINTER CHASING)
Tiap Node = 4 byte (Data) + 8 byte (Pointer 64-bit) = 12 byte (padded to 16 byte)

Alamat: 0x1040            Alamat: 0x48A0            Alamat: 0x20F0
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│ Data: 42      │         │ Data: 88      │         │ Data: 12      │
├───────────────┤         ├───────────────┤         ├───────────────┤
│ Next: 0x48A0 ──┼───┐     │ Next: 0x20F0 ──┼───┐     │ Next: NULL    │
└───────────────┘   │     └───────────────┘   │     └───────────────┘
                    │                         │
                    └─────────────────────────┘
  (Tiap lompatan pointer memicu DRAM Access Cycle baru karena perbedaan Cache Line)
```

### 2. Siklus Hidup Dynamic Array Geometric Growth

```
Kondisi Awal: Kapasitas = 2, Ukuran = 2
Alamat: 0xAA00
┌────────┬────────┐
│  VAL1  │  VAL2  │
└────────┴────────┘
  Cap=2, Size=2

Operasi: append(VAL3) -> Kapasitas Penuh!
1. Alokasi Buffer Baru: Kapasitas Baru = 2 * 2 = 4
2. Salin Elemen: 0xAA00 -> 0xBB00
3. Hapus Memori 0xAA00
4. Masukkan VAL3

Alamat Baru: 0xBB00
┌────────┬────────┬────────┬────────────────┐
│  VAL1  │  VAL2  │  VAL3  │  (Unallocated) │
└────────┴────────┴────────┴────────────────┘
  Cap=4, Size=3
```

### 3. Operasi Penyisipan Doubly Linked List dengan Sentinel Nodes

```
Keadaan Awal:
┌──────────────┐          ┌──────────────┐
│  SENTINEL    │  next    │  SENTINEL    │
│    HEAD      ├─────────►│    TAIL      │
│              │◄─────────┤              │
└──────────────┘  prev    └──────────────┘

Langkah Sisip Antara (Misal: Insert Node X):
1. Buat Node X.
2. X->next = Tail
3. X->prev = Head
4. Head->next = X
5. Tail->prev = X

Hasil Akhir:
┌──────────────┐          ┌──────────────┐          ┌──────────────┐
│  SENTINEL    │  next    │   NODE X     │  next    │  SENTINEL    │
│    HEAD      ├─────────►│  (Payload)   ├─────────►│    TAIL      │
│              │◄─────────┤              │◄─────────┤              │
└──────────────┘  prev    └──────────────┘  prev    └──────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi *Dynamic Array* minimal dalam C murni yang mengilustrasikan mekanisme manual alokasi memori, perhitungan kapasitas, dan analisis batas.

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

typedef struct {
    int *data;
    size_t size;
    size_t capacity;
} DynamicArray;

DynamicArray* da_create(size_t initial_capacity) {
    DynamicArray *da = (DynamicArray*)malloc(sizeof(DynamicArray));
    if (!da) return NULL;
    
    da->size = 0;
    da->capacity = initial_capacity > 0 ? initial_capacity : 2;
    da->data = (int*)malloc(da->capacity * sizeof(int));
    if (!da->data) {
        free(da);
        return NULL;
    }
    return da;
}

bool da_append(DynamicArray *da, int value) {
    if (da->size == da->capacity) {
        size_t new_capacity = da->capacity * 2;
        int *new_data = (int*)realloc(da->data, new_capacity * sizeof(int));
        if (!new_data) return false; // Alokasi gagal, array asli tetap aman
        
        da->data = new_data;
        da->capacity = new_capacity;
    }
    da->data[da->size++] = value;
    return true;
}

int da_get(const DynamicArray *da, size_t index, bool *out_status) {
    if (index >= da->size) {
        if (out_status) *out_status = false;
        return -1; // Out of bounds
    }
    if (out_status) *out_status = true;
    return da->data[index];
}

void da_destroy(DynamicArray *da) {
    if (da) {
        free(da->data);
        free(da);
    }
}

int main(void) {
    DynamicArray *arr = da_create(2);
    
    for (int i = 1; i <= 5; ++i) {
        da_append(arr, i * 10);
        printf("Appended %d | Size: %zu, Capacity: %zu\n", i * 10, arr->size, arr->capacity);
    }

    da_destroy(arr);
    return 0;
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Implementasi industri: **Doubly Linked List dengan Sentinel Nodes** yang thread-agnostic untuk engine subsistem kernel atau cache back-end. Implementasi ini menjamin operasi penyisipan dan penghapusan bernilai murni konstan $O(1)$ tanpa pemeriksaan pointer bersyarat ganda (*branchless boundary removal*).

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>

typedef struct DListNode {
    int64_t key;
    int64_t val;
    struct DListNode *prev;
    struct DListNode *next;
} DListNode;

typedef struct {
    DListNode *head; // Sentinel Head
    DListNode *tail; // Sentinel Tail
    size_t size;
} DoublyLinkedList;

DoublyLinkedList* dll_create(void) {
    DoublyLinkedList *list = (DoublyLinkedList*)malloc(sizeof(DoublyLinkedList));
    if (!list) return NULL;

    list->head = (DListNode*)malloc(sizeof(DListNode));
    list->tail = (DListNode*)malloc(sizeof(DListNode));
    if (!list->head || !list->tail) {
        free(list->head);
        free(list->tail);
        free(list);
        return NULL;
    }

    // Inisialisasi invariant sentinel
    list->head->prev = NULL;
    list->head->next = list->tail;
    list->tail->prev = list->head;
    list->tail->next = NULL;
    list->size = 0;

    return list;
}

DListNode* dll_push_front(DoublyLinkedList *list, int64_t key, int64_t val) {
    DListNode *node = (DListNode*)malloc(sizeof(DListNode));
    if (!node) return NULL;

    node->key = key;
    node->val = val;

    // Menghubungkan simpul baru di antara head dan elemen pertama nyata
    node->next = list->head->next;
    node->prev = list->head;
    
    list->head->next->prev = node;
    list->head->next = node;
    
    list->size++;
    return node;
}

void dll_remove_node(DoublyLinkedList *list, DListNode *node) {
    assert(node != list->head && node != list->tail); // Mencegah sentinel terhapus

    node->prev->next = node->next;
    node->next->prev = node->prev;

    free(node);
    list->size--;
}

DListNode* dll_pop_back(DoublyLinkedList *list) {
    if (list->size == 0) return NULL;

    DListNode *target = list->tail->prev;
    node_unlink:
        target->prev->next = list->tail;
        list->tail->prev = target->prev;
        list->size--;
        
    return target; // Kembalikan simpul untuk didaur ulang atau didealloc luar
}

void dll_destroy(DoublyLinkedList *list) {
    DListNode *curr = list->head;
    while (curr != NULL) {
        DListNode *next = curr->next;
        free(curr);
        curr = next;
    }
    free(list);
}

int main(void) {
    DoublyLinkedList *lru_tracker = dll_create();

    dll_push_front(lru_tracker, 101, 0xAA);
    dll_push_front(lru_tracker, 102, 0xBB);
    dll_push_front(lru_tracker, 103, 0xCC);

    printf("Jumlah simpul terdaftar: %zu\n", lru_tracker->size);

    DListNode *stale = dll_pop_back(lru_tracker);
    if (stale) {
        printf("Evicted LRU Element: Key %ld, Val 0x%lX\n", stale->key, stale->val);
        free(stale);
    }

    printf("Jumlah simpul setelah eviksi: %zu\n", lru_tracker->size);
    dll_destroy(lru_tracker);
    return 0;
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Evaluasi | Array Statis | Dynamic Array | Singly Linked List | Doubly Linked List |
| :--- | :--- | :--- | :--- | :--- |
| **Akses Berdasarkan Indeks** | $O(1)$ | $O(1)$ | $O(N)$ | $O(N)$ |
| **Penyisipan / Penghapusan Awal** | $O(N)$ | $O(N)$ | $O(1)$ | $O(1)$ |
| **Penyisipan / Penghapusan Akhir** | $O(1)$ | $O(1)$ amortized | $O(1)$ jika ada Tail | $O(1)$ |
| **Penyisipan / Penghapusan Tengah** | $O(N)$ | $O(N)$ | $O(1)$ (Pointer diketahui) | $O(1)$ (Pointer diketahui) |
| **Memori Overhead** | Nol ($0$ byte per elemen) | Kapasitas tak terpakai ($Cap - Size$) | $1 \text{ Pointer}$ ($8$ byte / node pada 64-bit) | $2 \text{ Pointer}$ ($16$ byte / node pada 64-bit) |
| **Spatial Locality & Cache Behavior**| Sangat Tinggi (L1/L2 hits) | Sangat Tinggi (L1/L2 hits) | Sangat Buruk (High miss rate) | Terburuk (Chasing pointer ganda) |
| **Beban Memory Allocator** | Nol (Ditentukan saat kompilasi) | Rendah ($\log N$ kali relokasi) | Sangat Tinggi ($N$ alokasi `malloc`) | Sangat Tinggi ($N$ alokasi `malloc`) |

### Aturan Pengambilan Keputusan Arsitektur:
1. **Pilih Dynamic Array secara default.** Dalam rekayasa perangkat lunak modern, throughput CPU jauh lebih sering dibatasi oleh *memory bandwidth* daripada operasi logika. Kemampuan Dynamic Array untuk memanfaatkan *CPU cache-line fetching* menjadikannya lebih cepat daripada Linked List secara empiris, bahkan untuk operasi penyisipan linear pada kumpulan data ribuan elemen.
2. **Pilih Doubly Linked List hanya jika:**
   * Diperlukan jaminan latensi puncak (*strictly bounded real-time deadlines*) di mana relokasi amortisasi $O(N)$ dari dynamic array tidak dapat ditoleransi sama sekali.
   * Ukuran memori dari objek yang ditampung sangat masif, sehingga biaya menyalin objek saat dynamic array berekspansi jauh lebih mahal daripada alokasi pointer.
   * Elemen sering disisipkan dan dihapus di tengah struktur, dan referensi pointer langsung ke elemen target sudah dipegang secara persisten oleh sistem lain (contoh: *LRU Cache* terintegrasi dengan Hash Map).

---

## SEKSI 11 — BEST PRACTICES

### Dynamic Array
* **Pre-allocate Memory (`reserve` pattern):** Jika estimasi ukuran akhir diketahui, panggil fungsi reservasi kapasitas di muka untuk mengeliminasi operasi penyalinan memori berkali-kali.
* **Pertahankan Faktor Pertumbuhan Geometris antara 1.5 hingga 2.0:** Menggandakan ukuran sebesar $2.0\times$ adalah standar historis, namun $1.5\times$ (digunakan oleh MSVC STL) atau $1.618\times$ (Golden Ratio) memungkinkan alokator memori mendaur ulang segmen heap yang didealokasikan sebelumnya.
* **Gunakan `memmove` atau `memcpy` untuk Operasi Bulk:** Hindari menyalin elemen secara manual menggunakan perulangan elemen demi elemen (`for-loop`). Manfaatkan instruksi vektor SIMD yang dioptimalkan dalam `memmove`.

### Linked List
* **Gunakan Sentinel Nodes (Dummy Nodes):** Selalu inisialisasi simpul kepala dan ekor tiruan. Ini mengeliminasi seluruh logika pencabangan `if (head == NULL)` atau `if (curr->next == NULL)` sehingga kode lebih tahan bug dan terhindar dari *branch misprediction*.
* **Manajemen Alokasi Berkelompok (Object Pool / Arena Allocator):** Jangan mengeksekusi `malloc()` individual untuk setiap penambahan node. Alokasikan simpul-simpul dalam sebuah blok array besar (*chunked allocator*) untuk mempertahankan lokalitas spasial dan memangkas fragmentasi memori heap.
* **Nol-kan Pointer Pasca Dealokasi:** Selalu terapkan pola *defensive programming* dengan menyetel pointer ke `NULL` setelah `free(node)` untuk mendeteksi *dangling pointer* secara deterministik.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Naive Arithmetic Resizing
```c
// BENCANA PERFORMA: Kompleksitas ekspansi menjadi O(N^2)
void push_bad(DynamicArray *da, int val) {
    if (da->size == da->capacity) {
        da->capacity += 1; // Menambah hanya 1 elemen
        da->data = (int*)realloc(da->data, da->capacity * sizeof(int));
    }
    da->data[da->size++] = val;
}
```
*Dampak:* Setiap penyisipan akan memicu alokasi ulang dan penyalinan memori yang proporsional terhadap ukuran data saat itu. Memasukkan $100.000$ elemen akan menyalin sekitar 5 miliar elemen.

### 2. Memory Leak saat Kegagalan `realloc`
```c
// BUG FATAL: Jika realloc gagal (NULL), pointer lama hilang dan bocor ke sistem
da->data = realloc(da->data, new_capacity * sizeof(int)); 
```
*Solusi:* Tampung hasil pada pointer temporer. Jika bernilai valid, perbarui pointer utama.

### 3. Pointer Dereferencing pada Linked List Terputus
```c
// KESALAHAN URUTAN OPERASI: Rantai data hilang selamanya
void insert_after(Node *prev_node, int val) {
    Node *new_node = malloc(sizeof(Node));
    new_node->data = val;
    
    prev_node->next = new_node;        // SALAH! Alamat node berikutnya terputus di sini
    new_node->next = prev_node->next;  // new_node sekarang menunjuk ke dirinya sendiri!
}
```
*Solusi:* Simpan alamat `prev_node->next` ke `new_node->next` terlebih dahulu sebelum memperbarui relasi pointer milik `prev_node`.

### 4. Pointer Chasing Traversal Overhead
Melakukan traversal linked list secara berulang hanya untuk mencari elemen ke-$i$ di dalam perulangan bersarang:
```c
for (int i = 0; i < n; i++) {
    // get_at_index melakukan traversal dari awal list setiap pemanggilan: O(N^2)
    process(get_at_index(linked_list, i)); 
}
```
*Solusi:* Gunakan pola *Iterator* atau navigasi langsung via pointer `curr = curr->next`.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: In-Place Singly Linked List Reversal (Level: Fondasional)
* **Tantangan:** Tulis fungsi C murni `void reverse_list(Node **head_ref)` yang membalikkan urutan simpul *Singly Linked List* secara *in-place*.
* **Batasan:** Kompleksitas waktu wajib $\Theta(N)$ dan kompleksitas ruang tambahan wajib $\Theta(1)$ (tidak boleh mengalokasikan array pembantu ataupun menggunakan rekursi heap/stack).

### Latihan 2: Shrink-to-Fit Implementation dengan Anti-Thrashing Guard (Level: Intermediate)
* **Tantangan:** Rancang fungsi `pop_back` pada *Dynamic Array*. Jika rasio elemen yang tersisa turun melewati ambang batas tertentu, kapasitas harus menyusut setengahnya.
* **Perangkap:** Jika kapasitas dipotong setengah saat ukuran array mencapai tepat 50%, serangkaian operasi `push` dan `pop` bolak-balik pada batas tersebut akan menyebabkan *thrashing* (alokasi dan dealokasi terus-menerus bernilai $O(N)$). 
* **Tugas:** Buktikan dan implementasikan ambang batas penyusutan yang menjamin biaya operasi tetap amortisasi $O(1)$ (misal: susutkan ke kapasitas separuh hanya ketika `size <= capacity / 4`).

### Latihan 3: Deteksi Siklus Siklik pada Pointer (Level: Algoritmik Lanjutan)
* **Tantangan:** Diberikan pointer awal dari sebuah Linked List yang kemungkinan telah rusak dan memiliki siklus melingkar (*cyclic reference*). Implementasikan algoritma deteksi loop Floyd (*Tortoise and Hare Algorithm*) tanpa memodifikasi isi data atau mengalokasikan hash set.
* **Output:** Kembalikan pointer yang merujuk tepat pada simpul pertama dimulainya siklus tersebut.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Sebuah sistem melakukan $1.024$ operasi penyisipan ke dalam Dynamic Array kosong berkapasitas awal $1$ dengan faktor ekspansi $2.0$. Berapa kali alokasi memori baru terjadi sepanjang proses tersebut?**
   * A. 10 kali
   * B. 11 kali
   * C. 512 kali
   * D. 1.024 kali

2. **Dilihat dari mekanisme pengalamatan perangkat keras, mengapa traversal array jauh lebih cepat daripada traversal linked list dengan jumlah elemen dan tipe payload yang identik?**
   * A. Array menggunakan memori virtual, sedangkan Linked List menggunakan memori fisik.
   * B. Array mengeksekusi operasi SIMD di register, sedangkan Linked List selalu tertahan di ALU.
   * C. Array memiliki lokalitas spasial kontinu yang memicu perangkat keras CPU mengisi Cache Line secara otomatis, meminimalkan latensi *Cache Miss*.
   * D. Array tidak memerlukan komputasi aritmetika penambahan alamat.

3. **Berapa jumlah memori tambahan (overhead pointer murni) yang terbuang pada arsitektur komputer 64-bit untuk menyimpan $1.000.000$ data bilangan bulat 32-bit (`int`) jika diimplementasikan menggunakan Doubly Linked List dibandingkan menggunakan Flat Array statis?**
   * A. Sekitar 4 Megabyte
   * B. Sekitar 8 Megabyte
   * C. Sekitar 16 Megabyte
   * D. Sekitar 24 Megabyte

4. **Kapan operasi penyisipan pada Dynamic Array bernilai $O(N)$ dalam analisis kasus terburuk (*worst-case*)?**
   * A. Ketika array baru saja diinisialisasi pertama kali.
   * B. Ketika kapasitas array saat ini telah terisi penuh, memaksa terjadinya realokasi heap dan pemindahan salinan seluruh elemen lama.
   * C. Ketika penyisipan dilakukan pada indeks terdepan dari array yang kosong.
   * D. Ketika tipe data yang disimpan berupa pointer.

5. **Apa fungsi utama penyertaan Sentinel Nodes (Dummy Head dan Dummy Tail) pada implementasi Doubly Linked List industri?**
   * A. Menyimpan metrik statistik panjang list secara terdistribusi.
   * B. Mengeliminasi seluruh pengecekan kasus batas dereferensi pointer `NULL` saat menyisipkan atau menghapus simpul.
   * C. Memampatkan memori heap agar tidak terfragmentasi.
   * D. Mencegah algoritma sorting mengalami dereferensi siklik.

---

### KUNCI JAWABAN & EVALUASI
* **1. Jawaban: A.** Kapasitas berkembang mengikuti deret pangkat dua: $1 \to 2 \to 4 \to 8 \to 16 \to 32 \to 64 \to 128 \to 256 \to 512 \to 1024$. Perpindahan kapasitas terjadi pada pemanggilan ke-2, 3, 5, 9, 17, 33, 65, 129, 257, 513. Total alokasi baru $= 10$ kali.
* **2. Jawaban: C.** Sifat memori kontigu memungkinkan CPU prefetcher bekerja optimal mengantisipasi data berikutnya ke CPU cache line.
* **3. Jawaban: C.** Pada sistem 64-bit, satu pointer berukuran 8 byte. Satu simpul Doubly Linked List membutuhkan 2 pointer (`next` dan `prev`) $= 16$ byte pointer overhead. Untuk $10^6$ node: $10^6 \times 16 \text{ byte} \approx 16 \text{ MB}$ (belum memperhitungkan alignment padding alokator malloc).
* **4. Jawaban: B.** Kasus terburuk absolut (worst-case individual) adalah tepat saat kapasitas habis dan operasi penyalinan array sepanjang $N$ dijalankan, menghasilkan waktu eksekusi $O(N)$, meskipun secara agregat teramortisasi $O(1)$.
* **5. Jawaban: B.** Sentinel node menjamin pointer `node->prev` dan `node->next` tidak akan pernah menunjuk ke `NULL` pada simpul operasional manapun, sehingga mutasi pointer bebas dari instruksi seleksi kondisi tepi.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Teks Wajib:**
  * Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to Algorithms* (4th ed.). MIT Press. — **Bab 10: Elementary Data Structures & Bab 17: Amortized Analysis**.
  * Knuth, D. E. (1997). *The Art of Computer Programming, Volume 1: Fundamental Algorithms* (3rd ed.). Addison-Wesley. — **Bagian 2.2: Linear Lists**.
* **Makalah Klasik & Sistem Tingkat Rendah:**
  * Drepper, Ulrich. (2007). *What Every Programmer Should Know About Memory*. Red Hat, Inc. (Wajib baca untuk korelasi CPU Caches dengan manipulasi data structures).
* **Repositori & Standar Industri:**
  * LLVM Project: `llvm::SmallVector` Implementation internals (Contoh hybrid dynamic array optimasi cache).
  * Linux Kernel Source Tree: `include/linux/list.h` (Implementasi standard circular intrusive doubly linked list kernel).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Prinsip Kontigu vs Terpisah:** Array mengorbankan fleksibilitas mutasi ukuran demi kecepatan komputasi instan $O(1)$ indexing dan pemanfaatan optimal *CPU Cache hierarchy*. Sebaliknya, Linked List mengorbankan lokalitas memori dan efisiensi ruang demi kecepatan mutasi $O(1)$ lokal simpul yang independen dari pergeseran elemen memori lainnya.
2. **Kekuatan Ekspansi Geometris:** Dynamic Array mempertahankan biaya rata-rata penyisipan sebesar $O(1)$ amortized hanya jika kapasitas dikalikan secara rasio eksponensial (misal $\times 2$). Penambahan kapasitas secara linier/aritmetika mendegradasi performa sistem menjadi bencana komputasi kuadratik $O(N^2)$.
3. **Hardware-Aware Design:** Analisis teoritis kompleksitas Big-O harus ditinjau ulang bersama realitas arsitektur perangkat keras modern: sebuah pencarian linear $O(N)$ pada flat array berurutan sering kali berjalan jauh lebih cepat daripada algoritma yang secara teoritis identik pada Linked List karena minimnya *CPU Cache Misses*.
4. **Disiplin Rekayasa List:** Implementasi Linked List skala industri harus mengadopsi struktur simpul *Sentinel* untuk meniadakan kompleksitas penanganan kasus ujung pointer (`NULL checks`) dan menekan tingkat kesalahan *segfault* struktural.

---

## SEKSI 17 — GLOSARIUM

* **Amortized Analysis:** Metode analisis biaya algoritma di mana serangkaian operasi diperhitungkan secara agregat untuk menunjukkan bahwa rata-rata biaya per operasi bernilai rendah, meskipun ada operasi individual tunggal yang berbiaya sangat tinggi.
* **Cache Line:** Unit pertukaran data terkecil antara memori utama (RAM) dan sistem CPU Cache; umumnya berukuran 64 byte pada arsitektur x86/ARM kontemporer.
* **Spatial Locality:** Karakteristik perilaku eksekusi sistem di mana pengaksesan suatu alamat memori fisik menandakan bahwa alamat-alamat memori yang bersebelahan dengannya kemungkinan besar akan diakses dalam waktu dekat.
* **Pointer Chasing:** Kondisi degradasi performa di mana CPU tidak dapat memprediksi alamat memori komputasi berikutnya sebelum membaca dan mengevaluasi pointer yang termuat pada simpul saat ini.
* **Sentinel Node:** Simpul struktural tiruan yang disisipkan secara permanen di awal atau akhir dari rantai linked list untuk mempermudah operasi penyisipan dan pemotongan simpul.
* **Thrashing:** Kondisi degradasi ekstrem di mana sumber daya mesin habis terkuras hanya untuk melayani siklus alokasi, dealokasi, dan penataan ulang memori secara berulang-ulang tanpa menghasilkan kemajuan eksekusi tugas utama.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Penyampaian Pedagogis:** Jangan izinkan mahasiswa menguji performa Linked List vs Array hanya dengan $100$ data! Buat sesi praktikum laboratorium di mana mahasiswa mengukur durasi traversal pada $10.000.000$ elemen integer. Mahasiswa akan menyaksikan secara langsung bahwa Array berjalan ribuan persen lebih cepat, meruntuhkan asumsi pemula yang sering mendewakan linked list.
* **Fokus Audit Memori:** Wajibkan mahasiswa menggunakan *tooling* instrumentasi memori (seperti `Valgrind` atau LLVM `AddressSanitizer / ASan`) saat mengerjakan latihan implementasi Linked List di C untuk mendeteksi sedini mungkin adanya kebocoran heap, pembebasan memori ganda (*double free*), ataupun akses ruang liar (*out-of-bounds*).
* **Diskusi Kritis Kelas:** Ajak kelas memperdebatkan mengapa `std::vector` pada C++ modern hampir selalu dianjurkan daripada `std::list`, dan dalam skenario riil apa saja anggapan ini dapat dipatahkan.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal Rilis | Penulis / Reviewer | Deskripsi Perubahan |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | 2026-03-30 | CS Curriculum Architecture Board | Rilis perdana modul berstandar rekayasa sistem mendalam |
| **v1.0.1** | 2026-04-02 | Systems & Architecture SIG | Penambahan visualisasi Cache Line dan perbaikan formula ekspansi aritmetika |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** [CS-FND-0304: Analisis Asimptotik Kompleksitas Algoritma dan Master Theorem](../03-Analisis-Algoritma/module-04.md)
* **Modul Saat Ini:** **CS-FND-0401: Representasi Memori, Array Statis, Dynamic Array, dan Linked List**
* **Modul Berikutnya:** [CS-FND-0402: Stack, Queue, dan Implementasi Ring Buffer Berbasis Alokasi Kontigu](module-02.md)