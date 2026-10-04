# Algorithmic Mastery & Technical Problem Solving (LeetCode Curriculum)

Selamat datang di kurikulum **Algorithmic Mastery & Technical Problem Solving**. Silabus ini dirancang secara sistematis untuk mentransformasi cara berpikir Anda dari sekadar menghafal solusi (*pattern memorization*) menjadi penguasaan intuitif dan formal terhadap struktur data, variasi algoritma, analisis kompleksitas asimtotik, dan rekayasa performa sistem pada skala industri.

---

## 1. Course Overview & Mindset

### The Engineering Mindset: Beyond LeetCode
Banyak engineer gagal dalam wawancara teknis atau penulisan kode produksi berkinerja tinggi karena mereka mendekati algoritma sebagai teknik menghafal pola (*pattern matching* buta). Kurikulum ini dibangun di atas prinsip-prinsip inti berikut:

1. **Structural Invariants & Mathematical Guarantees**
   Algoritma bukan sekumpulan trik bahasa pemrograman; algoritma adalah manipulasi matematis dari sekumpulan invarian (*loop invariants*, *topological order*, *optimal substructure*). Setiap modul menuntut pembuktian formal kebenaran logika (*correctness*) sebelum optimasi dilakukan.
2. **Space-Time Trade-offs & Hardware Symbiosis**
   Analisis asimtotik $O(N)$ tidak cukup. Anda akan menganalisis penggunaan memori pada tingkat perangkat keras: *cache locality*, *pointer chasing overhead*, alokasi memori heap vs stack, dan konsekuensi amortisasi struktur data dinamis.
3. **Problem Space Deconstruction**
   Setiap masalah kompleks dipecah menjadi primitif: identifikasi representasi *state*, batas transisi, topologi graf tersembunyi, atau struktur matematis yang mendasarinya (seperti *monotonicity* atau sifat *greedy choice*).
4. **Production-Ready Implementation**
   Kode yang benar tidak hanya lolos *test cases*, tetapi juga harus tahan terhadap *integer overflow*, *stack overflow* akibat rekursi dalam, kebocoran memori, dan skenario *edge cases* ekstrem ($\varnothing$, nilai batas, siklus tak terduga).

---

## 2. Learning Roadmap

```plaintext
LeetCode Mastery Curriculum
│
├── 01. Array & Hashing Architecture
│   ├── 01-array-amortization-and-memory-layouts
│   └── 02-hashmap-internals-and-collision-resolution
│
├── 02. Two Pointers & Sliding Window Mechanics
│   ├── 01-converging-and-parallel-pointers
│   └── 02-dynamic-and-fixed-sliding-windows
│
├── 03. Monotonic Structures & Stack Execution
│   ├── 01-stack-state-machine-and-evaluations
│   └── 02-monotonic-stack-and-monotonic-queue
│
├── 04. Binary Search & Divide and Conquer
│   ├── 01-binary-search-over-continuous-and-discrete-spaces
│   └── 02-divide-and-conquer-and-inversion-counting
│
├── 05. Pointer Manipulation & Linked Lists
│   ├── 01-pointer-mutation-and-cycle-detection
│   └── 02-lru-and-lfu-cache-architectures
│
├── 06. Trees & Hierarchical State Traversal
│   ├── 01-recursive-iterative-tree-traversals
│   ├── 02-binary-search-tree-invariants
│   └── 03-tree-serialization-and-lowest-common-ancestors
│
├── 07. Graph Theory & Network Topologies
│   ├── 01-traversal-bfs-dfs-and-cycle-detection
│   ├── 02-union-find-disjoint-set-forests
│   └── 03-shortest-paths-and-topological-ordering
│
├── 08. Priority Queues, Heaps & Advanced Intervals
│   ├── 01-binary-heap-internals-and-k-way-merging
│   └── 02-interval-scheduling-and-sweep-line-algorithms
│
├── 09. Dynamic Programming & Exhaustive Search
│   ├── 01-backtracking-pruning-and-combinatorics
│   ├── 02-one-dimensional-and-two-dimensional-dp
│   └── 03-knapsack-bitmask-and-interval-dp
│
└── 10. Advanced Structures & Specialized Paradigms
    ├── 01-prefix-trees-trie-and-bit-manipulation
    └── 02-segment-trees-and-binary-indexed-trees-fenwick
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Array & Hashing Architecture](./01-array-hashing)
Fokus pada mekanika memori kontigu, amortisasi alokasi vektor, implementasi tabel hash murni, penanganan kolisi, dan manipulasi *prefix/suffix*.
*   [01. Array Amortization and Memory Layouts](./01-array-hashing/01-array-amortization-and-memory-layouts.md)
*   [02. HashMap Internals and Collision Resolution](./01-array-hashing/02-hashmap-internals-and-collision-resolution.md)

### [Bab 02: Two Pointers & Sliding Window Mechanics](./02-two-pointers-sliding-window)
Menguasai optimasi reduksi kompleksitas dari $O(N^2)$ ke $O(N)$ melalui teknik penunjuk ganda dan jendela komputasi dinamis/statis berbasis invarian.
*   [01. Converging and Parallel Pointers](./02-two-pointers-sliding-window/01-converging-and-parallel-pointers.md)
*   [02. Dynamic and Fixed Sliding Windows](./02-two-pointers-sliding-window/02-dynamic-and-fixed-sliding-windows.md)

### [Bab 03: Monotonic Structures & Stack Execution](./03-monotonic-structures-stack)
Analisis mendalam mengenai *call stack*, parser bahasa formal (*expression parsing*), serta pemanfaatan struktur monotonik untuk optimasi pencarian batas elemen.
*   [01. Stack State Machine and Evaluations](./03-monotonic-structures-stack/01-stack-state-machine-and-evaluations.md)
*   [02. Monotonic Stack and Monotonic Queue](./03-monotonic-structures-stack/02-monotonic-stack-and-monotonic-queue.md)

### [Bab 04: Binary Search & Divide and Conquer](./04-binary-search-divide-conquer)
Formulasi predikat kebenaran monotonik, pencarian biner pada ruang solusi abstrak kontinu/diskrit, dan perancangan algoritma partisi rekursif.
*   [01. Binary Search Over Continuous and Discrete Spaces](./04-binary-search-divide-conquer/01-binary-search-over-continuous-and-discrete-spaces.md)
*   [02. Divide and Conquer and Inversion Counting](./04-binary-search-divide-conquer/02-divide-and-conquer-and-inversion-counting.md)

### [Bab 05: Pointer Manipulation & Linked Lists](./05-pointer-manipulation-linked-lists)
Navigasi referensi memori eksplisit, manipulasi pointer non-alokatif, algoritma deteksi siklus Floyd, dan penggabungan struktur data majemuk.
*   [01. Pointer Mutation and Cycle Detection](./05-pointer-manipulation-linked-lists/01-pointer-mutation-and-cycle-detection.md)
*   [02. LRU and LFU Cache Architectures](./05-pointer-manipulation-linked-lists/02-lru-and-lfu-cache-architectures.md)

### [Bab 06: Trees & Hierarchical State Traversal](./06-trees-hierarchical-traversal)
Manipulasi struktur hierarkis pohon biner, invariant struktur pencarian (*BST*), algoritma serialisasi/deserialisasi, dan perhitungan jalur ancestral.
*   [01. Recursive and Iterative Tree Traversals](./06-trees-hierarchical-traversal/01-recursive-iterative-tree-traversals.md)
*   [02. Binary Search Tree Invariants](./06-trees-hierarchical-traversal/02-binary-search-tree-invariants.md)
*   [03. Tree Serialization and Lowest Common Ancestors](./06-trees-hierarchical-traversal/03-tree-serialization-and-lowest-common-ancestors.md)

### [Bab 07: Graph Theory & Network Topologies](./07-graph-theory-topologies)
Representasi matriks dan *adjacency list*, algoritma penelusuran ruang keadaan, deteksi komponen terhubung kuat, partisi partisi disjoin, dan perutean terpendek.
*   [01. Traversal (BFS/DFS) and Cycle Detection](./07-graph-theory-topologies/01-traversal-bfs-dfs-and-cycle-detection.md)
*   [02. Union-Find Disjoint Set Forests](./07-graph-theory-topologies/02-union-find-disjoint-set-forests.md)
*   [03. Shortest Paths and Topological Ordering](./07-graph-theory-topologies/03-shortest-paths-and-topological-ordering.md)

### [Bab 08: Priority Queues, Heaps & Advanced Intervals](./08-priority-queues-intervals)
Struktur *complete binary tree*, pemeliharaan heap invarian, strategi multi-stream merge, geometri komputasi dasar, dan algoritma *sweep-line*.
*   [01. Binary Heap Internals and K-Way Merging](./08-priority-queues-intervals/01-binary-heap-internals-and-k-way-merging.md)
*   [02. Interval Scheduling and Sweep-Line Algorithms](./08-priority-queues-intervals/02-interval-scheduling-and-sweep-line-algorithms.md)

### [Bab 09: Dynamic Programming & Exhaustive Search](./09-dynamic-programming-search)
Reduksi ruang pencarian eksponensial: *backtracking* terpangkas, formalisasi persamaan Bellman, pemetaan submasalah tumpang tindih (*memoization/tabulation*), hingga optimasi ruang keadaan.
*   [01. Backtracking, Pruning, and Combinatorics](./09-dynamic-programming-search/01-backtracking-pruning-and-combinatorics.md)
*   [02. One-Dimensional and Two-Dimensional DP](./09-dynamic-programming-search/02-one-dimensional-and-two-dimensional-dp.md)
*   [03. Knapsack, Bitmask, and Interval DP](./09-dynamic-programming-search/03-knapsack-bitmask-and-interval-dp.md)

### [Bab 10: Advanced Structures & Specialized Paradigms](./10-advanced-structures-paradigms)
Akselerasi operasi string menggunakan *Prefix Trees*, manipulasi representasi level-bit, dan penanganan kueri rentang dinamis (*range queries*) berkinerja tinggi.
*   [01. Prefix Trees (Trie) and Bit Manipulation](./10-advanced-structures-paradigms/01-prefix-trees-trie-and-bit-manipulation.md)
*   [02. Segment Trees and Binary Indexed Trees (Fenwick)](./10-advanced-structures-paradigms/02-segment-trees-and-binary-indexed-trees-fenwick.md)

---

## 4. Capstone Project: High-Throughput In-Memory Order Matching & Analytics Engine

Sebagai kulminasi dari penguasaan algoritma tingkat lanjut, Anda akan merancang dan mengimplementasikan **High-Throughput In-Memory Order Matching & Real-Time Analytics Engine** murni dari *scratch* tanpa pustaka pihak ketiga untuk struktur data intinya.

### Deskripsi Masalah
Bursa aset finansial membutuhkan mesin pencocokan order (*matching engine*) dengan latensi sub-mikrodetik yang mampu mengeksekusi limit order, market order, serta membatalkan order secara instan, sembari memelihara analitik agregat pasar secara *real-time*.

### Persyaratan Teknis & Spesifikasi Algoritma

1. **Order Book Core Data Structures (Limit Order Book)**
   *   Implementasikan struktur data buku pesanan *Bids* (beli) dan *Asks* (jual).
   *   Buku pesanan harus mendukung operasi:
       *   `AddLimitOrder(price, quantity, side)` dalam $O(\log M)$ atau $O(1)$ amortized di mana $M$ adalah jumlah unik *price levels*.
       *   `CancelOrder(order_id)` dalam $O(1)$ deterministik menggunakan mapping Hash/Array pointer ke simpul *Doubly Linked List*.
       *   `MatchOrders()` mengeksekusi prinsip FIFO (*Price-Time Priority*) dengan throughput minimal $\ge 500.000$ operasi per detik.
2. **Real-time Range Volume Queries (Analytics Engine)**
   *   Implementasikan **Segment Tree** atau **Fenwick Tree (Binary Indexed Tree)** untuk menjawab agregat volume likuiditas:
       *   `QueryVolumeInRange(min_price, max_price)` dalam batas waktu $O(\log P)$ di mana $P$ adalah batas rentang harga.
       *   Pembaruan agregasi dinamis saat eksekusi terjadi dalam $O(\log P)$.
3. **Sliding Window Volatility & Analytics Tracker**
   *   Menggunakan varian **Monotonic Queue** dan **Sliding Window**, hitung volatilitas harga real-time (Maksimum, Minimum, dan Median Transaksi) dalam jendela waktu geser $W$ transaksi terakhir dengan kompleksitas $O(1)$ amortized per transaksi.
4. **Symbol & Routing Trie**
   *   Implementasikan **Trie Structure** khusus untuk perutean simbol instrumen dan validasi sintaks order secara instan ($O(K)$ di mana $K$ adalah panjang string kode simbol).

### Batasan Kinerja & Non-Fungsional
*   **Zero Dynamic Allocation Hot-Path**: Seluruh simpul struktur data (*doubly-linked nodes*, *tree nodes*) wajib menggunakan strategi *memory arena* / *object pooling* teralokasi di awal untuk mencegah *garbage collection pause* atau fragmentasi memori heap.
*   **Memory Footprint**: Maksimum footprint memori $128\text{ MB}$ untuk menampung $1.000.000$ order aktif.
*   **Latency Profile**: P99 Latency pencocokan transaksi harus berada di bawah $10\text{ }\mu\text{s}$ (mikrodetik) pada simulasi benchmark beban tinggi.
*   **Verifikasi Kebenaran**: Dilengkapi *harness test* otomatis yang memvalidasi *loop invariants*, *data race absence* (jika diterapkan secara konkuren), dan determinisme status buku order melawan model komputasi matematis.