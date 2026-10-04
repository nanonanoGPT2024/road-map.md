# BAB 06: Quiz, Challenge, & Knowledge Check
**Trees & Hierarchical State Traversal**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Memory Layout & Call Stack Mechanics pada DFS Traversal:**
   Jelaskan secara mendalam representasi memori pada proses rekursi *Depth-First Search* (Pre-order, In-order, Post-order) di runtime engine (misal: JVM atau V8). Apa yang sebenarnya terjadi pada *stack frame*, register pointer, dan alokasi memori saat traversal dilakukan pada pohon yang degenerasi (*skewed tree*) dengan kedalaman $N = 100.000$, dan mengapa teknik *Tail Call Optimization* (TCO) umumnya tidak dapat mengeliminasi *overhead* rekursi pada struktur data *Binary Tree* standar?

2. **Morris Traversal vs Iterative Traversal Menggunakan Explicit Stack:**
   Bandingkan arsitektur *Morris Traversal* dengan traversal iteratif berbasis struktur data *Stack* eksplisit. Jelaskan mekanisme modifikasi pointer (*threaded binary tree*) yang memungkinkan Morris Traversal mencapai kompleksitas ruang $O(1)$ amortized tanpa merusak topologi pohon permanen. Kapan Morris Traversal **dilarang keras** digunakan di sistem *multi-threaded production*?

3. **Trade-off Kompleksitas Ruang: BFS (Queue) vs DFS (Stack):**
   Diberikan sebuah *Complete Binary Tree* dengan $N$ *nodes*. Analisis secara matematis konsumsi memori puncak (*peak auxiliary memory*) untuk traversal menggunakan *Breadth-First Search* (BFS) dibandingkan dengan *Depth-First Search* (DFS). Pada rasio *branching factor* ($k$) dan kedalaman ($d$) seperti apa BFS menjadi bottleneck memori yang fatal dibandingkan DFS?

4. **Karakteristik Invariant & Validasi Binary Search Tree (BST):**
   Mengapa pengujian lokal sederhana `node.left.val < node.val < node.right.val` gagal memvalidasi keabsahan struktur BST secara global? Jelaskan perancangan algoritma validasi BST berbasis *range propagation* $(-\infty, +\infty)$ vs *in-order state tracking*, serta analisis bagaimana penanganan batas ekstrem seperti tipe data integer 32-bit (`Integer.MIN_VALUE` / `Integer.MAX_VALUE`) harus diimplementasikan tanpa menyebabkan *integer overflow*.

5. **Hierarchical Traversal State Aggregation (Tree DP):**
   Dalam konteks *Dynamic Programming on Trees* (Tree DP) seperti problem *Tree Diameter* atau *Binary Tree Maximum Path Sum*, jelaskan mengapa pendekatan *bottom-up* (Post-order aggregation) merupakan satu-satunya paradigma yang optimal ($O(N)$). Jelaskan perbedaan mendasar antara *state value* yang dikembalikan ke node induk (*parent*) versus *global answer state* yang di-update pada setiap sub-root.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Debugging StackOverflow & Heap Exhaustion pada Serialisasi AST:**
   Sebuah *parser engine* memproses struktur Abstract Syntax Tree (AST) berbasis JSON. Pada payload tertentu dengan kedalaman nesting ekstrem, sistem melempar `StackOverflowError`. Seorang engineer mengubah implementasi traversal menjadi iteratif menggunakan explicit `ArrayDeque`, namun sistem justru mengalami `OutOfMemoryError: Java heap space`. Analisis akar masalah struktural ini dan jelaskan strategi mitigasi traversal hierarki untuk beban kerja tanpa batas kedalaman (*unbounded depth*).

2. **Corner Cases pada Algoritma Lowest Common Ancestor (LCA):**
   Diberikan dua node target $p$ dan $q$ pada Binary Tree umum:
   ```
          3
         / \
        5   1
       /
      6
   ```
   Jika implementasi rekursif LCA standar mengembalikan node saat `root == p || root == q`, skenario anomali apa yang muncul jika node $q$ ternyata **tidak eksis** di dalam pohon? Bagaimana memodifikasi state traversal agar algoritma mampu membedakan antara "LCA ditemukan", "Hanya satu node ditemukan", dan "Kedua node tidak saling terhubung", tetap dalam satu kali pass ($O(N)$ waktu dan $O(H)$ ruang)?

3. **Cache Invalidation & Pointer Chasing Overhead:**
   Sebuah array berukuran $N$ dialokasikan secara kontigu, sedangkan *pointer-based Binary Tree* mengalokasikan node secara dinamis via *heap allocator*. Mengapa traversal pada *heap-allocated Binary Tree* berukuran besar mengalami degradasi performa $5\times$ hingga $20\times$ lebih lambat dibanding traversal pada array berukuran byte yang sama, meskipun kompleksitas teoritis keduanya identik $O(N)$? Kaitkan jawaban Anda dengan *CPU L1/L2/L3 Cache lines*, *Translation Lookaside Buffer* (TLB) *misses*, dan *pointer chasing*.

4. **Edge Cases Rekonstruksi Pohon (Serialization / Deserialization):**
   Mengapa rekonstruksi struktur pohon biner unik **wajib** menyertakan penanda node kosong (*null/sentinel tokens*) jika menggunakan satu jenis traversal saja (misal: Pre-order saja), TETAPI **tidak membutuhkan** penanda *null* jika menggunakan kombinasi traversal In-order + Pre-order (dengan asumsi semua nilai node unik)? Jelaskan skenario di mana rekonstruksi In-order + Pre-order tetap akan gagal jika duplikasi nilai node diperbolehkan.

5. **Subtree Hashing & Isomorphism Detection:**
   Untuk mendeteksi sub-pohon yang identik (*duplicate subtrees*) secara efisien dalam waktu $O(N)$, teknik serialisasi string sering kali digunakan (misal: `"L,R,Val"`). Jelaskan mengapa konkatenasi string naive pada traversal Post-order menyebabkan kompleksitas waktu terdegradasi menjadi $O(N^2)$ pada pohon degenerasi, dan bagaimana teknik *Merkle Tree Hashing* atau *Node-ID Mapping with Tuple Interning* mereduksi kompleksitas tersebut kembali ke $O(N)$ konstan.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Traversal AST Skala Besar (Insiden Produksi)
Sebuah platform Code Security Scanner mengevaluasi file monolitik berukuran 50 MB dengan mengonversinya menjadi AST (Abstract Syntax Tree) yang memiliki sekitar 8 juta node. Microservice AST Analyzer ditulis dalam Go/Rust dan berjalan di container dengan alokasi memori terbatas (2 GB RAM). Saat scan dijalankan:
- CPU utilization melonjak ke 100% (dominan *garbage collection pause* dan page faults).
- Container terbunuh oleh Linux kernel OOM Killer (*Exit Code 137*).
- Profiling awal menunjukkan struktur node tree konvensional mengonsumsi 64 byte per node hanya untuk pointer overhead:
  ```go
  type Node struct {
      Type     NodeType
      Value    string
      Children []*Node
      Parent   *Node
  }
  ```

*Pertanyaan Diagnostik:*
1. Mengapa alokasi heap dinamis per node dan field `Parent *Node` menjadi destruktif terhadap memori dan *Garbage Collector* pada skala 8 juta node?
2. Rancang ulang representasi memori pohon tersebut menggunakan teknik flattened memory layout (*Data-Oriented Design* / *Arena Allocation* / *Index-based Left-Child Right-Sibling representation*). Berapa estimasi penghematan memori yang bisa dicapai dan bagaimana pola traversal DFS diadaptasi?

---

### Skenario B: Race Condition & Data Corruption pada Concurrent Tree Updates (RBAC Engine)
Sebuah sistem *Role-Based Access Control* (RBAC) menyimpan hirarki organisasi dan *permission inheritance* dalam struktur n-ary tree in-memory terdistribusi. Node dapat dipindahkan (*re-parenting*) secara real-time via API administratif menggunakan operasi mutasi:
```
MoveNode(nodeId, newParentId)
```
Di bawah beban konkurensi tinggi:
- Terjadi insiden di mana sebuah thread memindahkan Node $A$ ke bawah Node $B$, sementara secara simultan thread lain memindahkan Node $B$ ke bawah Node $A$.
- Akibatnya, sub-pohon tersebut terlepas dari root utama dan membentuk struktur sirkular (*cyclic graph / deadloop*).
- Worker thread yang menjalankan traversal evaluasi izin (`checkPermission(userId, action)`) terjebak dalam *infinite loop*, menyebabkan CPU starvation total pada seluruh cluster node.

*Pertanyaan Diagnostik:*
1. Identifikasi kegagalan protokol konkurensi dan jelaskan mengapa locking granular level-node (fine-grained locking) rentan memicu *deadlock* atau *cyclic references* pada pohon hierarkis.
2. Rancang algoritma deteksi siklus atomik atau mekanisme validasi topologi *lock-free / copy-on-write* (COW) yang menjamin operasi mutasi pohon hierarkis selalu menghasilkan *Directed Acyclic Graph* (DAG) yang valid tanpa mengorbankan performa read-traversal throughput tinggi.

---

### Skenario C: Trade-off Arsitektur Dynamic Prefix Indexing (Trie vs FST vs Inverted Index)
Sebuah platform e-commerce memproses 200.000 query per detik (QPS) untuk fitur *autocomplete search*. Dataset terdiri dari 50 juta kata kunci pencarian unik dengan metadata bobot relevansi (*weight/score*). Sistem saat ini menggunakan in-memory standard Trie node pointer:
- Memory footprint mencapai 48 GB (terlalu mahal untuk replikasi multi-region).
- Update frekuensi tinggi (sekitar 5.000 kata kunci di-update/insert per detik berdasarkan tren pembelian).

*Pertanyaan Diagnostik:*
1. Analisis perbandingan arsitektural antara:
   - **Pointer-based Trie**
   - **Radix Tree (Compressed Trie)**
   - **Finite State Transducer (FST)**
2. Jika sistem membutuhkan latensi pencarian prefix $P99 < 2\text{ ms}$, memory usage $< 8\text{ GB}$, dan tetap mendukung *near-real-time updates*, arsitektur hierarki mana yang Anda pilih? Jelaskan trade-off konsumsi memori, latensi lookup, dan kompleksitas mutasi konkuren dari pilihan Anda.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Concurrent Virtual File System (VFS) Path Resolver & Permission Aggregator

#### Problem Statement
Anda diminta untuk membangun core in-memory engine untuk sebuah Virtual File System (VFS) berkinerja tinggi. Engine ini harus mampu merepresentasikan direktori hierarkis hingga kedalaman maksimum 128 level, menangani jutaan path file, mengevaluasi izin akses file berbasis pewarisan hierarkis (*inherited permissions*), serta mengeksekusi *path resolution* secara thread-safe tanpa memblokir pembacaan concurrent.

#### Requirements
1. **Representasi Pohon Hierarkis (In-Memory Directory Tree):**
   - Implementasikan struktur data pohon yang efisien untuk memetakan path absolut (contoh: `/var/log/audit/2026/03/syslog.log`).
   - Setiap node direktori dapat memiliki metadata izin: `READ`, `WRITE`, `EXECUTE`, atau `INHERIT` (mewarisi izin parent).
2. **Operasi yang Harus Didukung:**
   - `mkdir_p(path, permissions)`: Membuat direktori beserta parent yang belum ada secara atomik.
   - `move(src_path, dest_path)`: Memindahkan direktori atau file ke lokasi baru. Operasi ini **wajib memvalidasi bahwa `dest_path` bukan merupakan keturunan (*descendant*) dari `src_path`** (mencegah siklus).
   - `resolve_permission(path, user_context)`: Mengembalikan izin efektif untuk path target melalui traversal Post-order/Top-down aggregation dari root ke target node.
   - `calculate_disk_usage(path)`: Mengembalikan total ukuran direktori (akumulasi Post-order Tree DP dari seluruh file dalam sub-tree).
3. **Konkurensi & Safety:**
   - Multi-reader, single-writer atau fully concurrent non-blocking reads. Operasi `resolve_permission` dan `calculate_disk_usage` tidak boleh diblokir oleh mutasi path di cabang (*branch*) pohon yang berbeda.
   - Sistem tidak boleh menggunakan global lock pada keseluruhan pohon saat mutasi berlangsung.

#### Constraints
- Waktu lookup path (`resolve_permission`): Maksimal $O(K)$, di mana $K$ adalah jumlah komponen direktori pada path target (tidak bergantung pada total node $N$ di seluruh pohon).
- Memory overhead: Tidak boleh melebihi 120 byte per node file/direktori.
- Anti-Recursion: Operasi penghitungan disk usage pada sub-pohon yang sangat dalam ($K \ge 10.000$ jika terjadi degenerasi) dilarang menggunakan rekursi implisit untuk mencegah Call Stack Overflow.

#### Expected Output
1. Implementasi kode bersih (Clean, idiomatic TypeScript, Java, Go, atau Rust) yang modular dan runnable.
2. Unit tests yang mencakup:
   - Skenario *deep nested path creation* dan *traversal resolution*.
   - Deteksi dan penolakan upaya *cyclic move* (contoh: memindahkan `/a` ke `/a/b/c`).
   - Verifikasi isolasi *concurrent read-write* (pembacaan izin tetap konsisten saat subtree lain sedang dipindahkan).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme pemanggilan stack frame pada rekursi dan konversi formal algoritma rekursif menjadi bentuk iteratif berbasis explicit stack.
- [ ] Batasan trade-off memori antara BFS ($O(\text{Width})$) dan DFS ($O(\text{Depth})$) pada berbagai bentuk pohon (*balanced*, *bushy*, hingga *skewed*).
- [ ] Prinsip invarian BST global dan teknik propagasi batas (*boundary constraints*) vs *in-order predecessor/successor validation*.
- [ ] State management pada Tree DP: memisahkan hasil agregasi sub-tree yang diteruskan ke atas (*return value*) dengan hasil evaluasi global path yang melintasi sub-root.
- [ ] Karakteristik *Memory Locality* dan dampak struktural alokasi pointer pada *CPU cache efficiency* (*pointer chasing vs flat array buffer*).
- [ ] Algoritma Lowest Common Ancestor (LCA) berbasis traversal tunggal ($O(N)$) serta optimasinya menggunakan *Binary Lifting* ($O(N \log N)$ preprocessing, $O(\log N)$ query).
- [ ] Mekanisme pencegahan siklus (*cycle prevention*) saat melakukan modifikasi topologi hierarki secara real-time.

### Saya tidak perlu menghafal:
- [ ] Sintaks mutasi rotasi AVL/Red-Black Tree yang kaku (cukup pahami konsep invariant self-balancing dan balance factor).
- [ ] Implementasi internal algoritma parsing AST spesifik compiler tertentu.
- [ ] Magic numbers atau hash seeds tertentu yang digunakan pada Merkle Tree string hashing.

### Saya harus bisa melakukan:
- [ ] Mengonversi algoritma DFS rekursif kompleks apa pun menjadi bentuk iteratif aman (*non-stack-overflowing*) menggunakan explicit stack dan tracking state pointer.
- [ ] Menulis traversal BFS berbasis level-by-level processing menggunakan size snapshot loop tanpa membuat multiple queue instances.
- [ ] Melakukan serialisasi dan deserialisasi struktur pohon biner maupun n-ary secara lossless ke dalam bentuk byte-stream atau string dengan kompleksitas linier $O(N)$.
- [ ] Mengidentifikasi dan membuktikan keberadaan bug tersembunyi (*off-by-one*, penanganan nilai duplikat, dan *cyclic reference*) pada kode hierarki yang dibuat orang lain.
- [ ] Memilih dan mengimplementasikan representasi struktur data hierarkis yang tepat (Trie vs Compressed Radix vs Flat Memory Array) berdasarkan profil beban baca/tulis di level produksi.