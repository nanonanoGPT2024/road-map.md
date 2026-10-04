# BAB 05: POINTER MANIPULATION & LINKED LISTS
## MODULE 01: Dasar Manipulasi Pointer, Memory Layout, dan Sentinel Node Invariants

---

## SEKSI 01 — IDENTITAS MODUL

* **Kurikulum:** LeetCode Mastery & Data Structures Engine
* **Kategori:** 01-Core-Foundations
* **Bab:** 05 — Pointer Manipulation & Linked Lists
* **Modul:** 01 — Dasar Manipulasi Pointer, Memory Layout, dan Sentinel Node Invariants
* **Prasyarat:** Pemahaman alokasi memori dasar (Stack vs Heap), variabel referensi/pointer (Python/C++/Java), kompleksitas waktu & ruang Asimptotik ($O(1)$ vs $O(N)$).
* **Tingkat Kesulitan:** Beginner to Intermediate
* **Estimasi Waktu Penyelesaian:** 180 Menit

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis** representasi fisik linked list di dalam memori heap dan membandingkannya secara kuantitatif dengan contiguous array terkait *spatial locality* dan *cache performance*.
2. **Menguasai** urutan mutasi pointer (*pointer rewriting sequence*) tanpa memicu memory leak, *dangling pointer*, atau hilangnya akses (*lost reference*) ke sisa rantai node.
3. **Mengimplementasikan** teknik *Dummy Head* / *Sentinel Node* untuk mengeliminasi edge-cases percabangan kondisional pada operasi mutasi linked list.
4. **Membuktikan** kebenaran algoritma pembalikan list (*list reversal*) dan penghapusan node menggunakan *loop invariants*.
5. **Mengidentifikasi** dan memitigasi *infinite cycle* yang timbul akibat kesalahan penugasan pointer dereference.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [Pointer Manipulation Engine]
                                     |
         +---------------------------+---------------------------+
         |                                                       |
 [Memory Topology]                                    [Mutation Invariants]
         |                                                       |
  +------+------+                                         +------+------+
  |             |                                         |             |
Heap Non-    Pointer/Ref                               Pointer       Sentinel /
Contiguous   Dereference                               Rewiring      Dummy Nodes
Allocation   Semantics                                 Ordering           |
  |             |                                         |               |
Cache Miss   Indirection                               Isolasi       Eliminasi
Overhead     Cost ($O(1)$)                             Node Edge     Null-Checks
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada sistem komputasi modern, pemahaman terhadap *Linked List* bukan sekadar kemampuan menyelesaikan soal wawancara kerja, melainkan fondasi pemahaman bagaimana abstraksi memori berinteraksi dengan perangkat keras.

1. **Hardware & Cache Realities:** Array dialokasikan secara kontigu di memori, memanfaatkan *CPU L1/L2 cache prefetching* berkat prinsip *spatial locality*. Sebaliknya, linked list mengalokasikan node secara sporadis di heap. Mempelajari linked list melatih intuisi tentang *pointer chasing* dan latensi dereferensi memori tak teratur (*cache miss*).
2. **Dynamic Structural Mutation:** Tidak seperti array dinamis yang memerlukan realokasi $O(N)$ saat kapasitas terlampaui, linked list menjanjikan penyisipan dan penghapusan $O(1)$ *jika referensi node target telah diketahui*. Ini menjadikannya blok pembangun primitif untuk struktur data kompleks seperti *LRU Cache*, *Adjacency Lists pada Graf*, dan sistem alokasi kernel sistem operasi (misal: `list_head` pada Linux Kernel).
3. **Mental Model Precision:** Kode manipulasi pointer tidak memberikan ruang toleransi untuk kesalahan *off-by-one* atau kesalahan urutan eksekusi satu baris instruksi pun. Kesalahan satu baris dapat merusak keseluruhan struktur data (*lost reference* atau *cyclic traps*), menjadikannya domain terbaik untuk melatih ketelitian *state-tracking*.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Definisi Formal Singly Linked List
Singly Linked List adalah struktur data linier yang terdiri dari kumpulan node diskrit. Setiap node $u$ menyimpan payload data $\text{val}$ dan sebuah tautan uniter (*pointer* atau *reference*) $\text{next}$ yang menunjuk ke node suksesor $v$, sedemikian rupa sehingga:

$$\text{Node}(u) = \langle \text{val}_u, \text{next}_u \rangle \quad \text{dimana} \quad \text{next}_u \in \{\text{Node}, \text{NULL}\}$$

### 2. Node Singly vs Doubly vs Circular

| Tipe List | Pointer per Node | Overhead Memori (64-bit architecture) | Kemampuan Traversal |
| :--- | :--- | :--- | :--- |
| **Singly** | 1 (`next`) | $8\text{B payload} + 8\text{B pointer} = 16\text{B}$ min | Maju saja (Unidirectional) |
| **Doubly** | 2 (`prev`, `next`) | $8\text{B payload} + 16\text{B pointers} = 24\text{B}$ min | Maju & Mundur (Bidirectional) |
| **Circular** | 1 atau 2 (`tail.next = head`) | Sama dengan varian Singly / Doubly | Siklik tanpa terminator NULL |

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Manipulasi linked list murni bergantung pada eksekusi algoritma mutasi pointer dengan urutan yang strictly preserves references.

### Mekanisme 1: Penyisipan Node (Insertion)

Untuk menyisipkan node baru $N$ di antara node $A$ dan node $B$ ($A \to B$):

```
State Awal:     A ---------> B
Penyisipan:     A    N ---> B   (Langkah 1: N.next = A.next)
                A --/  N -> B   (Langkah 2: A.next = N)
Hasil:          A -> N ----> B
```

**Aturan Emas:** Jangan pernah mengubah `A.next` sebelum menugaskan `N.next = A.next`. Jika `A.next = N` dieksekusi lebih dulu, alamat node $B$ hilang dari memori (terjadi *lost reference* dan *memory leak* pada bahasa tanpa Garbage Collection).

### Mekanisme 2: Sentinel / Dummy Node Pattern

Salah satu kompleksitas terbesar algoritma linked list adalah penanganan *edge cases*:
- Manipulasi pada `head` (misalnya menghapus head, menyisipkan elemen baru sebelum head).
- Manipulasi list kosong (`head == NULL`).
- List dengan hanya satu elemen.

**Sentinel Node (Dummy Head)** adalah node non-fungsional yang dialokasikan di awal list untuk bertindak sebagai *anchor* permanen:

```
[ Dummy Node ] -> [ Node 1 (Real Head) ] -> [ Node 2 ] -> NULL
```

Dengan sentinel node, operasi pada elemen pertama list memiliki semantik mutasi yang identik dengan operasi pada elemen tengah, meniadakan percabangan `if (head == NULL)` atau `if (curr == head)`.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Topologi Memori: Contiguous Array vs Linked List di Heap

```
CONTIGUOUS ARRAY DI MEMORI (L1/L2 Cache Friendly)
Alamat Fisik:  0x1000   0x1004   0x1008   0x100C   0x1010
Memori:       [ Val A ][ Val B ][ Val C ][ Val D ][ Val E ]
               ^-------- Cache Line Prefetch mengambil semua sekaligus

LINKED LIST DI HEAP (Spatial Cache Inefficient)
Alamat Fisik:  0x10A0            0x24F0            0x1008
Heap Node:    [ Val A | 0x24F0 ] [ Val C | NULL   ] [ Val B | 0x24F0 ]
                         |                           ^
                         +---------------------------+
               (Cache miss terjadi di setiap lompatan dereferensi pointer)
```

### 2. Trace Pembalikan Pointer In-Place (In-Place Reversal)

```
Kondisi Awal:
prev = NULL
curr = Head (Node A)

      NULL      [ A ]  -->  [ B ]  -->  [ C ]  --> NULL
       ^          ^
       |          |
      prev       curr

Langkah Iterasi 1:
1. nxt = curr.next        (nxt menunjuk B)
2. curr.next = prev       (A.next diputus dari B, diarahkan ke NULL)
3. prev = curr            (prev maju ke A)
4. curr = nxt             (curr maju ke B)

      NULL <-- [ A ]        [ B ]  -->  [ C ]  --> NULL
                 ^            ^
                 |            |
                prev         curr
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

### Masalah: Membalik Singly Linked List (In-Place Reversal)
*Ref: LeetCode 206 — Reverse Linked List*

#### Implementasi Python 3

```python
from typing import Optional

class ListNode:
    def __init__(self, val: int = 0, next: Optional['ListNode'] = None):
        self.val = val
        self.next = next

def reverse_list(head: Optional[ListNode]) -> Optional[ListNode]:
    """
    Membalik Singly Linked List secara in-place.
    
    Loop Invariant:
    Pada awal setiap iterasi, sublist sebelum node 'curr' telah berhasil dibalik
    dan memiliki 'prev' sebagai head barunya. Sublist dari 'curr' hingga akhir
    belum dimodifikasi.
    """
    prev: Optional[ListNode] = None
    curr: Optional[ListNode] = head
    
    while curr is not None:
        # 1. Simpan referensi ke node suksesor
        next_temp: Optional[ListNode] = curr.next
        
        # 2. Balikkan arah pointer
        curr.next = prev
        
        # 3. Geser window invariant satu langkah ke kanan
        prev = curr
        curr = next_temp
        
    return prev
```

#### Implementasi C++ (RAII & Explicit Pointers)

```cpp
struct ListNode {
    int val;
    ListNode *next;
    ListNode() : val(0), next(nullptr) {}
    ListNode(int x) : val(x), next(nullptr) {}
    ListNode(int x, ListNode *next) : val(x), next(next) {}
};

class Solution {
public:
    ListNode* reverseList(ListNode* head) {
        ListNode* prev = nullptr;
        ListNode* curr = head;
        
        while (curr != nullptr) {
            ListNode* nextTemp = curr->next;
            curr->next = prev;
            prev = curr;
            curr = nextTemp;
        }
        
        return prev;
    }
};
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Masalah: Menghapus Node ke-N dari Akhir List (One-Pass dengan Dummy Head)
*Ref: LeetCode 19 — Remove Nth Node From End of List*

Jika list memiliki panjang $L$, node yang dihapus berada di indeks $L - n$. Pendekatan konvensional memerlukan dua kali traversal (pass pertama menghitung $L$, pass kedua menghapus). Kita dapat menyelesaikannya dalam **satu pass** ($O(N)$ waktu, $O(1)$ ruang) menggunakan teknik **Fast & Slow Pointer** dikombinasikan dengan **Sentinel Node**.

#### Algoritma:
1. Inisialisasi `dummy` node yang menunjuk ke `head`.
2. Letakkan pointer `fast` dan `slow` pada `dummy`.
3. Majukan pointer `fast` sebanyak $n + 1$ langkah, menciptakan celah (*gap*) sebesar $n$ node antara `fast` dan `slow`.
4. Geser kedua pointer maju satu langkah per iterasi hingga `fast` mencapai `nullptr`.
5. Pointer `slow` kini berada persis sebelum node target yang harus dihapus. Lakukan dereferensi: `slow.next = slow.next.next`.

```python
class Solution:
    def removeNthFromEnd(self, head: Optional[ListNode], n: int) -> Optional[ListNode]:
        # Sentinel node mengeliminasi penanganan khusus saat menghapus elemen head
        dummy = ListNode(0, head)
        fast: Optional[ListNode] = dummy
        slow: Optional[ListNode] = dummy

        # Majukan fast sejauh n + 1 langkah untuk menjaga jarak
        for _ in range(n + 1):
            if fast is None:
                return head # Kasus defensif jika n melebihi ukuran list
            fast = fast.next

        # Geser kedua pointer hingga fast melewati batas list
        while fast is not None:
            fast = fast.next
            slow = slow.next  # type: ignore (slow dijamin bukan None)

        # Mutasi pointer: bypass node target
        if slow and slow.next:
            slow.next = slow.next.next

        return dummy.next
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Evaluasi | Contiguous Array (`std::vector` / Python `list`) | Singly Linked List |
| :--- | :--- | :--- |
| **Akses Elemen ($i$-th index)** | $O(1)$ via kalkulasi offset langsung | $O(N)$ penelusuran sequential dari `head` |
| **Penyisipan di Head** | $O(N)$ pergeseran seluruh elemen | $O(1)$ alokasi & penugasan pointer |
| **Penyisipan di Arbitrary Node** | $O(N)$ pergeseran memori | $O(1)$ mutasi pointer (jika lokasi node diketahui) |
| **Overhead Memori** | Nol overhead pointer (hanya *amortized buffer*) | Tambahan 8-16 byte pointer untuk setiap payload |
| **CPU Cache Utilization** | **Sangat Tinggi**; data dimuat ke *cache line* | **Sangat Rendah**; rentan terhadap *cache misses* |
| **Alokasi Memori** | Blok kontigu besar (dapat memicu kegagalan alokasi memori fragmented) | Alokasi kecil terfragmentasi (mudah dialokasikan di heap) |

---

## SEKSI 11 — BEST PRACTICES

1. **Selalu Gunakan Sentinel Node untuk Konstruksi Dinamis:** Bila Anda membangun list baru dari awal atau memodifikasi kepala list secara dinamis, selalu alokasikan dummy head:
   ```python
   dummy = ListNode(-1)
   tail = dummy
   # ... bangun list via tail.next ...
   return dummy.next
   ```
2. **Explicit Memory Sanitization (C++):** Dalam bahasa tanpa GC, pemutusan node dari list tidak menghapus node tersebut dari memori fisik. Tangani dealokasi secara eksplisit:
   ```cpp
   ListNode* toDelete = slow->next;
   slow->next = slow->next->next;
   delete toDelete; // Mencegah memory leak
   ```
3. **Isolasi Node yang Diekstrak:** Ketika memindahkan sebuah node $X$ dari satu list ke list lain, pastikan memutuskan `X->next = nullptr` sebelum menyambungkannya, guna mencegah terbentuknya siklus secara tak terduga.
4. **Verifikasi `None`/`nullptr` Dereference:** Terapkan pemeriksaan bertingkat: selalu validasi ketersediaan `curr` sebelum mengecek `curr.next`, dan validasi `curr.next` sebelum membaca `curr.next.next`.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Pointer Overwriting (Lost Reference Trap)
```python
# KESALAHAN FATAL:
# Niat: Menyisipkan new_node di antara curr dan curr.next
curr.next = new_node          # Referensi asli ke curr.next HILANG!
new_node.next = curr.next     # new_node.next malah menunjuk ke dirinya sendiri (Cyclic Loop!)

# SOLUSI BENAR:
new_node.next = curr.next
curr.next = new_node
```

### 2. Null Pointer Dereference pada Traversal Cepat
```cpp
// KESALAHAN:
while (fast->next != nullptr) { // Crash jika fast sejak awal adalah nullptr!
    fast = fast->next->next;    // Crash jika fast->next bukan nullptr, tetapi bernilai valid sedangkan fast->next->next tidak ada!
}

// SOLUSI BENAR:
while (fast != nullptr && fast->next != nullptr) {
    fast = fast->next->next;
}
```

### 3. Kehilangan Head Asli Tanpa Sentinel
```python
# Modifikasi langsung variabel head saat iterasi:
while head:
    head = head.next
return head # KESALAHAN: Mengembalikan None karena pointer head telah tergeser habis!
```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Exercise 1 (Easy): Merge Two Sorted Lists (LeetCode 21)
* **Tugas:** Gabungkan dua sorted singly linked list `l1` dan `l2` menjadi satu list baru yang terurut secara monotonik naik tanpa membuat node baru (gunakan kembali node yang ada).
* **Target Kompleksitas:** Time $O(N + M)$, Space $O(1)$.
* **Constraint:** Gunakan Sentinel Node pattern untuk menangani konstruksi output list.

### Exercise 2 (Medium): Swap Nodes in Pairs (LeetCode 24)
* **Tugas:** Diberikan sebuah singly linked list, lakukan penukaran setiap dua node yang bersebelahan secara *in-place*. Modifikasi nilai integer di dalam node tidak diperbolehkan; hanya mutasi pointer yang legal.
* **Invariant Guide:** Gambarkan diagram pointer perpindahan dari 4 komponen: `prev`, `first`, `second`, dan `first.next`.

### Exercise 3 (Hard): Reverse Nodes in k-Group (LeetCode 25)
* **Tugas:** Diberikan linked list, balikkan node-node di dalamnya per kelompok berukuran $k$ elemen. Jika jumlah node yang tersisa bukan kelipatan $k$, biarkan node tersebut tetap dalam urutan aslinya.
* **Constraint:** $O(1)$ auxiliary space complexity. Rekursi yang mengonsumsi stack frames $O(N/k)$ tidak diperkenankan.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa implikasi performa dari CPU Cache Miss pada penelusuran linked list dibandingkan array?**
   * A. Linked list selalu lebih cepat karena ukuran node lebih kecil.
   * B. Linked list memicu latensi memori tinggi karena alamat heap yang non-kontigu menggagalkan operasi spatial prefetching pada CPU L1/L2 cache.
   * C. Array memiliki latency lebih buruk karena harus memuat padding metadata.
   * D. Tidak ada perbedaan karena keduanya menggunakan arsitektur RAM yang sama.
   * *Jawaban:* **B**.

2. **Diberikan sequence kode mutasi pointer berikut:**
   ```python
   temp = curr.next
   curr.next = temp.next
   temp.next = head
   ```
   **Apa yang sedang terjadi secara struktural?**
   * A. Node `curr` dihapus dari list.
   * B. Node suksesor dari `curr` dipindahkan ke posisi paling depan list sebagai head baru.
   * C. Terjadi infinite loop antara `curr` dan `head`.
   * D. Terjadi runtime error null pointer exception.
   * *Jawaban:* **B**.

3. **Mengapa inisialisasi dummy node `dummy = ListNode(0, head)` sangat disarankan pada operasi penghapusan node?**
   * A. Mempercepat algoritma dari $O(N)$ menjadi $O(1)$.
   * B. Mengalokasikan array cadangan di cache layer.
   * C. Menghilangkan kebutuhan logika percabangan khusus (`if`) ketika node yang harus dihapus adalah elemen pertama (`head`).
   * D. Mengurangi konsumsi memori pointer.
   * *Jawaban:* **C**.

4. **Berapa banyak pointer mutasi minimum yang harus diubah per iterasi untuk membalik singly linked list secara in-place?**
   * A. 1 pointer (`curr.next`) dibantu penyimpanan sementara satu referensi suksesor.
   * B. 3 pointer tanpa temporary variable.
   * C. Bergantung pada total panjang list.
   * D. 2 pointer sekaligus secara atomic.
   * *Jawaban:* **A**.

5. **Kondisi loop guard manakah yang benar untuk fast-slow pointer traversal ketika fast melangkah 2 unit dan slow melangkah 1 unit?**
   * A. `while (fast != NULL || fast->next != NULL)`
   * B. `while (fast != NULL && fast->next != NULL)`
   * C. `while (fast->next != NULL && fast->next->next != NULL)`
   * D. `while (slow != NULL && fast != NULL)`
   * *Jawaban:* **B**.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku:**
  * *Introduction to Algorithms (CLRS)*, 4th Edition — Bab 10: "Elementary Data Structures".
  * *The Art of Computer Programming (TAOCP)* Vol 1, Donald Knuth — "Information Structures: Linked Lists".
* **Makalah / Source Code Inti:**
  * Linux Kernel Documentation: `include/linux/list.h` — Implementasi Circular Intrusive Doubly-Linked List.
  * Ulrich Drepper: *"What Every Programmer Should Know About Memory"* — Bagian mengenai efek *Cache Line Latency* pada struktur linked pointer.
* **LeetCode Pattern Pathways:**
  * Tag: `Linked List`, Sub-pattern: `Two-Pointer / Sentinel Head`.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Linked list mengorbankan **spatial locality** dan akses indeks acak $O(1)$ demi penyisipan/penghapusan $O(1)$ lokal tanpa kebutuhan realokasi buffer memori secara kontigu.
2. Setiap operasi mutasi linked list mensyaratkan preservasi pointer suksesor via variabel temporary sebelum menulis ulang referensi target guna menghindari **lost reference traps**.
3. Penggunaan **Sentinel Node (Dummy Head)** adalah standar baku industri untuk menjamin invariant traversal, mengeliminasi percabangan kondisional *edge cases*, dan menyederhanakan kode secara drastis.
4. Mutasi pointer *in-place* menuntut pembuktian invariant yang ketat pada setiap langkah loop agar struktur data tidak terjebak dalam *infinite cycle* atau referensi `NULL` tak terkendali.

---

## SEKSI 17 — GLOSARIUM

* **Dereference:** Operasi mengakses lokasi memori aktual yang ditunjuk oleh sebuah pointer atau referensi address.
* **Sentinel Node / Dummy Head:** Node pembantu yang sengaja dialokasikan di depan atau di belakang list tanpa menyimpan data riil, dirancang untuk menyamaratakan operasi pada boundary list.
* **Spatial Locality:** Karakteristik eksekusi program di mana akses ke satu alamat memori fisik meningkatkan probabilitas akses ke alamat memori yang bersebelahan secara fisik dalam waktu dekat.
* **Pointer Chasing:** Kondisi di mana CPU terpaksa melakukan lookup memori serial berkali-kali karena setiap alamat berikutnya hanya diketahui setelah membaca data pointer saat ini, mematahkan eksekusi spekulatif dan instruction pipelining.
* **Loop Invariant:** Proposisi logika formal yang nilainya harus selalu benar sebelum dan sesudah setiap iterasi dari sebuah loop berlangsung.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Pedagogical Strategy:** Jangan biarkan peserta langsung menulis kode saat menangani masalah linked list. Wajibkan peserta untuk menggambar kotak dan tanda panah di atas kertas atau papan tulis terlebih dahulu. Validasi apakah urutan penghapusan/penyambungan panah menyebabkan node lain terputus tanpa referensi.
* **Debugging Mindset:** Tekankan bahwa bug pada manipulasi linked list hampir 90% berkorelasi dengan kegagalan eksekusi pada tiga kondisi ekstrem:
  1. Input adalah list kosong (`head == None`).
  2. Input hanya memiliki 1 elemen.
  3. Operasi dilakukan persis di node pertama (`head`) atau node terakhir (`tail`).
* **Visualisasi Debugger:** Rekomendasikan penggunaan ekstensi visualizer pointer saat sesi lab agar alur mutasi heap terlihat secara real-time.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal | Penulis | Deskripsi Perubahan |
| :--- | :--- | :--- | :--- |
| **1.0.0** | 2026-03-30 | Lead Curriculum Architect | Rilis draf materi foundational pointer invariants & Sentinel node pattern. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `[Bab 04 — Binary Search & Boundary Detection: Advanced Variants]`
* **Modul Saat Ini:** `[Bab 05 — Pointer Manipulation: Modul 01 — Dasar Manipulasi Pointer, Memory Layout, dan Sentinel Node Invariants]`
* **Modul Selanjutnya:** `[Bab 05 — Pointer Manipulation: Modul 02 — Two-Pointer Techniques: Fast-Slow & Cycle Detection (Floyd's Algorithm)]`