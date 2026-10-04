# BAB 03: Quiz, Challenge, & Knowledge Check
**Bab 03: Struktur Data Terhubung (Linked Lists, Pointer Manipulation, & Memory Locality)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Trade-off Memory Overhead & Cache Locality:**
   Secara teoritis, *insertion* pada sembarang posisi di *Singly Linked List* memiliki kompleksitas waktu $\mathcal{O}(1)$ jika *pointer* node referensi telah diketahui, dibandingkan $\mathcal{O}(n)$ pada *Dynamic Array* karena kebutuhan *shifting*. Namun, dalam arsitektur perangkat keras modern berorientasi CPU cache (L1/L2/L3) dan *hardware prefetcher*, jelaskan mengapa iterasi sekuensial dan mutasi pada *contiguous array* sering kali mengungguli *Linked List* bahkan pada skenario banyak mutasi. Hubungkan jawaban Anda dengan konsep *pointer chasing* dan *spatial locality*.

2. **Mekanisme Siklus: Floyd’s Cycle-Finding Algorithm (Tortoise and Hare):**
   Pada algoritma deteksi siklus Floyd, dua *pointer* bergerak dengan kecepatan berbeda ($v_{slow} = 1$ langkah, $v_{fast} = 2$ langkah). Buktikan secara matematis bahwa:
   * Jika siklus berukuran $C$ dan jarak dari *head* ke awal siklus adalah $K$, keduanya pasti akan bertemu di dalam siklus dengan kompleksitas waktu $\mathcal{O}(K + C)$.
   * Mengapa memindahkan salah satu *pointer* kembali ke *head* dan menjalankan keduanya dengan kecepatan 1 langkah akan mempertemukan mereka tepat di titik awal siklus (*cycle origin*)?

3. **Intrusive vs. Non-Intrusive Linked Lists:**
   Jelaskan perbedaan arsitektural antara implementasi standar non-intrusive linked list (misal: `std::list` di C++ atau `LinkedList<T>` di Java) dengan *Intrusive Linked List* (sebagaimana digunakan secara intensif di kernel Linux via `struct list_head`). Analisis implikasi keduanya terhadap fragmentasi memori *heap*, *cache misses*, dan penggunaan makro `container_of` (pointer arithmetic offset).

4. **Inversi Penunjuk (In-Place Pointer Reversal):**
   Dalam melakukan pembalikan (*reversal*) *Singly Linked List* secara in-place dengan ruang tambahan $\mathcal{O}(1)$, apa invariant state yang harus dipertahankan di setiap iterasi untuk mencegah hilangnya referensi memori (*dangling pointer/orphaned nodes*), dan mengapa pendekatan rekursif sering kali menjadi anti-pattern pada lingkungan produksi dengan batasan stack yang ketat (*stack overflow risk*)?

5. **Sentinel (Dummy) Nodes:**
   Evaluasi efektivitas penggunaan *Sentinel Node* (node dummy pada *head* dan/atau *tail*) dalam implementasi *Doubly Linked List*. Bagaimana pola desain ini mereduksi *cyclomatic complexity* dari kode mutasi data, dan apa trade-off memori minimal yang diakibatkannya?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **The ABA Problem pada Lock-Free Concurrent Linked List:**
   Dalam implementasi *lock-free stack* (Treiber Stack) atau *concurrent linked list* berbasis instruksi atomik `Compare-And-Swap` (CAS), jelaskan bagaimana skenario *ABA Problem* dapat terjadi dan menyebabkan kerusakan struktur memori (*use-after-free* atau korupsi penunjuk). Sebutkan dua mekanisme standar industri untuk memitigasinya.

2. **Memory Leak Diagnostik pada Garbage-Collected Runtimes:**
   Pada bahasa dengan managed memory (seperti Go atau Java), sebuah node *Doubly Linked List* dihapus dari rantai traversal utama dengan mengubah penunjuk `prev.next = next` dan `next.prev = prev`. Namun, profiler memori menunjukkan bahwa objek node tersebut beserta *payload* data besarnya tidak pernah dibersihkan oleh Garbage Collector. Mengapa kebocoran memori logis (*memory retention leak*) ini bisa terjadi, dan bagaimana solusinya?

3. **Debugging Memory Corruption via Valgrind/ASan:**
   Perhatikan cuplikan logika penghapusan node pada *Singly Linked List* berikut:
   ```c
   void delete_node(Node** head, int target) {
       Node* curr = *head;
       Node* prev = NULL;
       while (curr != NULL && curr->val != target) {
           prev = curr;
           curr = curr->next;
       }
       if (curr == NULL) return;
       prev->next = curr->next;
       free(curr);
   }
   ```
   Identifikasi *edge case* kritis di mana fungsi ini akan memicu *Segmentation Fault* (`NULL pointer dereference`) atau merusak *head pointer*. Tuliskan koreksi kode defensifnya.

4. **Cache-Friendly Chunked / Unrolled Linked List:**
   Untuk menjembatani jurang performa antara *Linked List* dan *Array*, para insinyur sistem menggunakan *Unrolled Linked List*. Jelaskan bagaimana struktur ini bekerja secara internal, bagaimana ukuran buffer per node ditentukan terhadap ukuran *CPU cache line* (umumnya 64 byte), dan bagaimana mekanisme rebalancing/splitting dilakukan saat operasi penambahan data.

5. **Deep Copy of Linked List with Random Pointers:**
   Diberikan struktur data linked list di mana setiap node memiliki dua pointer: `next` dan `random` (bisa menunjuk ke node mana pun atau `NULL`). Terdapat algoritma yang mampu menduplikasi struktur ini dalam $\mathcal{O}(n)$ waktu tanpa memerlukan alokasi *hash map* tambahan ($\mathcal{O}(1)$ auxiliary space). Jelaskan mekanisme interweaving (menyisipkan node kloning tepat di sebelah node asli) yang memungkinkan penyalinan pointer `random` secara presisi.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Latensi Spike pada Mesin Matching Engine Skala Besar
Sebuah platform pertukaran aset kripto memproses antrean order limit menggunakan *Doubly Linked List* in-memory untuk menyimpan order book per tingkat harga, di mana operasi penambahan dan pembatalan (*cancellation*) terjadi jutaan kali per detik. 

Setelah beban transaksi meningkat 5x lipat, sistem mulai mengalami lonjakan latensi persentil ke-99 (p99) dari 50 mikrodetik menjadi 15 milidetik, disertai *high page faults* dan saturasi memori sistem operasi akibat fragmentasi *heap*. Profiling menunjukkan alokasi dinamis (`malloc`/`free`) untuk setiap pembentukan objek `OrderNode` menjadi bottleneck utama.

* **Pertanyaan Diagnostik:**
  1. Analisis mengapa alokasi individual node per pesanan menghancurkan efisiensi memory allocator dan CPU L1/L2 caches.
  2. Rancang arsitektur alternatif pengganti alokasi dinamis individual node dengan tetap mempertahankan kompleksitas $\mathcal{O}(1)$ untuk *arbitrary node deletion* saat terjadi pembatalan order. (Petunjuk: Hubungkan dengan *Slab Allocator*, *Object Pool*, atau *Array-backed Indexed Linked List*).

---

### Skenario B: Data Inconsistency pada LRU Cache Concurrency Control
Sebuah tim backend mengimplementasikan sistem *Least Recently Used* (LRU) Cache kustom berbasis gabungan `HashMap` dan `Doubly Linked List`. Sistem dideploy pada arsitektur multi-threaded di mana setiap operasi `get(key)` memindahkan node yang diakses ke posisi terdepan (*head*) sebagai penanda *most recently used*.

Di bawah uji beban berat (*stress test*), sistem mengalami crash intermiten dengan pesan `SIGSEGV` saat melakukan traversal list, atau terjebak dalam *infinite loop*. Analisis *core dump* membuktikan bahwa terjadi modifikasi serentak (*race condition*) pada pointer `prev` dan `next`, menyebabkan siklus tak terduga (*corrupted links*).

* **Pertanyaan Diagnostik:**
  1. Jelaskan secara rinci skenario balapan (race condition) antara dua thread konkuren yang mengeksekusi `get()` pada dua node yang bersebelahan secara simultan.
  2. Evaluasi trade-off dari tiga strategi perbaikan berikut:
     * *Global Mutex Locking* pada seluruh struktur LRU.
     * *Fine-grained Node Locking* / Hand-over-hand locking.
     * *Read-Copy-Update* (RCU) atau arsitektur *Channel-based actor/Worker Thread Pool*. Manakah yang paling optimal untuk throughput pembacaan tinggi?

---

### Skenario C: Arsitektur Kernel-Level Intrusive List vs Virtual Memory Thrashing
Anda bertindak sebagai arsitek sistem operasi tertanam (*embedded real-time OS*). Subsistem manajemen memori harus melacak ribuan blok memori fisik yang dialokasikan menggunakan linked list. Karena batasan *RAM footprint* yang ekstrem (kurang dari 2 MB total), kegagalan alokasi memori akibat *out-of-memory* (OOM) tidak boleh terjadi saat menginisialisasi tracking metadata itu sendiri.

* **Pertanyaan Diagnostik:**
  1. Mengapa penggunaan linked list non-intrusif standar (yang memerlukan alokasi wrapper node baru setiap kali melacak elemen data baru) merupakan kelemahan arsitektur fatal untuk sistem ini?
  2. Gambarkan bagaimana *Intrusive Linked List* menyelesaikan masalah ketergantungan alokasi memori ini dengan menyematkan node pointer langsung di dalam payload struktur target. Bagaimana sistem menjamin bahwa operasi *linking* ke dalam tracking list tidak akan pernah gagal karena kekurangan memori?

---

## 4. Chapter Challenge

**Tantangan Praktis: High-Performance, Zero-Allocation, Thread-Safe LRU Eviction Engine**

### Deskripsi Masalah:
Rancang dan implementasikan mesin *eviction tracking* berbasis *Doubly Linked List* yang ditautkan dengan tabel indeks, yang ditujukan untuk sistem penyimpanan in-memory berperforma tinggi. Sistem ini harus meniadakan alokasi heap saat *runtime* (zero dynamic allocations during operations) dan meminimalisir dampak fragmentasi memori.

### Requirements:
1. **Struktur Data:**
   * Implementasikan *Doubly Linked List* terindeks yang menggunakan *flat pre-allocated memory pool* (Array of Nodes). Pointer node tidak boleh berupa penunjuk memori 64-bit mentah (`Node*`), melainkan indeks integer (misal: `uint32_t`) untuk menghemat konsumsi memori dan mengoptimalkan kompresi data.
   * Node *head* dan *tail* harus diinisialisasi menggunakan teknik *Sentinel Nodes* untuk menjamin nol percabangan kondisional (*branchless style programming*) pada boundary checks saat mutasi list.
2. **Operasi Inti:**
   * `void initialize(size_t capacity)`: Mengalokasikan array penampung secara utuh di awal.
   * `uint32_t access_node(uint32_t node_index)`: Memindahkan node yang dituju ke posisi *head* (menandai node sebagai yang paling baru digunakan) dalam $\mathcal{O}(1)$.
   * `uint32_t evict_oldest()`: Menghapus node tertua di *tail*, mengembalikan indeksnya agar dapat digunakan kembali oleh sistem penyimpanan, dalam $\mathcal{O}(1)$.
   * `void insert_new(uint32_t node_index)`: Memasukkan node baru yang dialokasikan dari pool ke posisi *head* dalam $\mathcal{O}(1)$.
3. **Constraints:**
   * **Memory Overhead:** Metadata overhead untuk list pointers per node tidak boleh melebihi 8 byte (4 byte untuk `next_index`, 4 byte untuk `prev_index`).
   * **Allocation Invariant:** Pasca pemanggilan `initialize()`, operasi `access_node`, `evict_oldest`, dan `insert_new` sama sekali dilarang memanggil `malloc`, `free`, `new`, atau operasi realokasi array dinamis.
   * **Correctness:** Operasi mutasi harus kebal terhadap kasus: kapasitas list terisi penuh, list hanya berisi 1 node, dan penghapusan berulang hingga list kosong.

### Expected Output:
* Kode implementasi fungsional (dalam C, C++, Rust, atau Go) yang mengimplementasikan spesifikasi di atas secara lengkap.
* Satu blok unit test yang menyimulasikan:
  1. Inisialisasi kapasitas 5 node.
  2. Pengisian 5 node hingga penuh.
  3. Akses berkala yang mengubah urutan prioritas (misal: node di tengah diakses).
  4. Penggusuran (*eviction*) 5 kali berturut-turut yang memvalidasi bahwa node dikeluarkan dalam urutan keusangan yang tepat (*exact LRU order*).
  5. Penggunaan kembali (*recycling*) indeks yang telah dieviasi tanpa ada kebocoran indeks.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Dampak arsitektur hardware modern (L1/L2/L3 cache misses, prefetching, TLB) terhadap kinerja traversal Linked List versus Contiguous Array.
- [ ] Aspek komputasi algoritma Floyd (Tortoise & Hare) untuk deteksi siklus, penentuan titik masuk siklus, dan pembuktian matematis konvergensinya.
- [ ] Perbedaan struktural, keunggulan performa, dan trade-off implementasi antara *Intrusive List* vs *Non-Intrusive List*.
- [ ] Mekanisme pembalikan penunjuk (*pointer manipulation*) secara in-place baik pada singly maupun doubly linked list tanpa alokasi memori tambahan.
- [ ] Pola penanganan *edge cases* (node kosong, single node, operasi boundary pada head/tail) menggunakan teknik *Sentinel (Dummy) Node*.
- [ ] Bahaya pointer dangling, memory retention leak pada runtime dengan GC, serta penanganan kasus konkurensi (seperti ABA Problem) pada pointer-based data structures.

### Saya tidak perlu menghafal:
- [ ] Implementasi variasi sintaks spesifik dari seluruh pointer syntax di berbagai bahasa pemrograman tingkat rendah.
- [ ] Rumus indeks eksplisit dari representasi binary heap di atas pointer, selama memahami konsep relasi parent-child.
- [ ] Kode template boilerplate dari library bawaan standar (seperti `std::list` STL atau `java.util.LinkedList`).

### Saya harus bisa melakukan:
- [ ] Menulis algoritma pembalikan linked list (*reverse linked list*) dan deteksi siklus secara akurat, bebas dari bug, dan *first-pass correct* tanpa bantuan IDE auto-complete.
- [ ] Mendiagnosis dan memperbaiki *Segmentation Fault*, *Memory Leak*, dan *Dangling Pointer* pada kode manipulasi pointer menggunakan debugging tools/profiler.
- [ ] Merancang struktur data linked-node berbasis array (*Array-backed / Pool-allocated Linked List*) untuk lingkungan sistem yang menuntut performa real-time dan bebas alokasi dinamis runtime.
- [ ] Memilih dengan tegas kapan harus menolak struktur data Linked List dan beralih ke Array-based structures (seperti Circular Ring Buffer atau Dynamic Vector) berdasarkan metrik akses memori dan profil beban kerja produksi.